# Labo 09 – Bases de données distribuées et verrous distribués : CockroachDB

<img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Ets_quebec_logo.png" width="250">

ÉTS - LOG430 - Architecture logicielle - Chargé de laboratoire : Gabriel C. Ullmann.

## 🎯 Objectifs d'apprentissage

- Comprendre le concept de **verrou distribué** (*distributed lock*) et pourquoi il est essentiel dans les systèmes distribués
- Observer comment CockroachDB distribue les données entre plusieurs nœuds via le **range-based sharding**
- Comparer les stratégies de verrouillage **pessimiste** et **optimiste** en termes de latence et de fiabilité
- Comprendre comment CockroachDB gère l'isolation **SERIALIZABLE** par défaut et les erreurs de sérialisation (SQLSTATE 40001)
- Mesurer le comportement du système sous forte concurrence avec des tests de charge
- Vérifier la **résilience** et la **cohérence des données** lors d'une panne de nœud

## ⚙️ Différences clés : CockroachDB vs YugabyteDB

| Aspect | YugabyteDB | CockroachDB |
|---|---|---|
| Protocol SQL | YSQL (PostgreSQL-compatible) | CRDB SQL (PostgreSQL-compatible) |
| Port SQL | 5433 | 26257 |
| Interface Admin | http://localhost:7000 | http://localhost:8080 |
| Sharding | Tablet-based | Range-based |
| Isolation par défaut | Read Committed | **Serializable** |
| Erreurs de contention | Moins fréquentes | SQLSTATE 40001 (à retenter) |
| Init du cluster | Automatique | Requiert `cockroach init` |

> 📝 **NOTE importante** : CockroachDB utilise l'isolation **SERIALIZABLE** par défaut, ce qui est plus strict que la plupart des bases de données. En cas de conflits entre transactions concurrentes, CockroachDB peut émettre une erreur `40001` (*serialization failure*) que l'application doit détecter et relancer. C'est pourquoi les deux stratégies (pessimiste et optimiste) incluent une boucle de retry dans ce projet.

## ⚙️ Setup

### 1. Clonez le dépôt

```bash
git clone https://github.com/[votrenom]/log430-labo9-cockroachdb
cd log430-labo9-cockroachdb
```

### 2. Créez un fichier .env

```sh
DB_HOST=cockroach1
DB_PORT=26257
DB_NAME=labo09
DB_USER=root
DB_PASSWORD=
```

### 3. Créez un réseau Docker

```bash
docker network create labo09-network
```

### 4. Démarrez l'environnement

```bash
docker compose build
docker compose up -d
```

> 📝 **NOTE** : Le conteneur `cluster-init` initialise le cluster CockroachDB (commande `cockroach init`), puis le conteneur `db-init` crée le schéma et insère les données de test. Les deux s'arrêtent automatiquement après leur exécution — c'est normal.

## 🧪 Activités pratiques

### 1. Observer le schéma et le cluster

1. Ouvrez http://localhost:8080 (**CockroachDB Admin UI**).

2. Allez dans l'onglet **Overview** et observez les nœuds du cluster. CockroachDB utilise le protocole **Raft** pour le consensus distribué : un nœud est élu *leaseholder* pour chaque *range* (plage de données), et les autres nœuds maintiennent des réplicas.

3. Dans l'onglet **Databases > labo09 > Tables**, explorez la table `stocks`. Contrairement au sharding par tablets de YugabyteDB, CockroachDB divise les données en **ranges** (intervalles de clés primaires), chacun répliqué sur plusieurs nœuds.

4. Vérifiez les données via l'onglet **Exec** du conteneur `cockroach1` dans Docker Desktop :

```sh
cockroach sql --insecure --host=cockroach1 --execute="SELECT * FROM labo09.orders;"
```

Exécutez le test de concurrence :

```bash
python tests/concurrency_test.py --threads 5 --product 3
```

Répétez la vérification pour confirmer la réplication :

```bash
# Sur cockroach1
cockroach sql --insecure --host=cockroach1 --execute="SELECT * FROM labo09.orders;"
# Sur cockroach2
cockroach sql --insecure --host=cockroach2 --execute="SELECT * FROM labo09.orders;"
# Sur cockroach3
cockroach sql --insecure --host=cockroach3 --execute="SELECT * FROM labo09.orders;"
```

> 💡 **Question 1** : Quelle est la sortie du terminal que vous obtenez? Si vous répétez cette commande sur `cockroach2` et `cockroach3`, est-ce que la sortie est identique? Illustrez votre réponse avec des captures d'écran du terminal.

### 2. Verrouillage pessimiste vs. optimiste

Dans ce laboratoire, nous étudierons deux approches pour éviter les **conditions de course** (*race conditions*) :

- **Verrouillage optimiste** : Chaque ligne de stock possède une colonne `version`. Une transaction lit la version courante, calcule la nouvelle quantité, puis effectue un `UPDATE` uniquement si la version correspond toujours. Si aucune ligne n'est affectée, la transaction recommence. Avec CockroachDB en mode SERIALIZABLE, la base peut également émettre une erreur `40001` — l'application la capture et relance aussi.

- **Verrouillage pessimiste** : La transaction acquiert un verrou au niveau de la ligne dès la lecture (`SELECT … FOR UPDATE`). CockroachDB supporte pleinement cette instruction. Toute autre transaction qui tente de toucher la même ligne sera **bloquée**. Même avec ce verrou, CockroachDB peut occasionnellement émettre une erreur `40001` sous très forte contention, d'où la présence d'un retry dans les deux stratégies.

Lisez `src/write_order.py` pour voir les implémentations. Exécutez le test de concurrence :

```bash
python tests/concurrency_test.py --threads 20 --product 3
```

L'article ID 3 a un stock initial de 2 unités. Avec 20 threads simultanés, seules 2 commandes devraient être acceptées.

Vérifiez le stock final :

```bash
curl http://localhost:5000/stocks
```

> 💡 **Question 2** : Observez la latence moyenne des deux approches. Laquelle a la latence la plus élevée et pourquoi? Illustrez votre réponse avec les sorties du terminal.

> 💡 **Question 3** : Répétez le test avec 5 threads. Qui a la latence la plus élevée maintenant et pourquoi? Illustrez votre réponse avec les sorties du terminal.

> 💡 **Question bonus** : Comparez le comportement de CockroachDB (SERIALIZABLE par défaut) avec YugabyteDB (Read Committed par défaut) en termes de fréquence des retries. Quel impact cela a-t-il sur la conception de l'application?

### 3. Test de charge avec Locust

1. Réinitialisez les stocks :
```bash
curl -X POST http://localhost:5000/stocks/reset
```

2. Ouvrez l'interface Locust à http://localhost:8089.

3. Configurez un test avec **50 utilisateurs**, *spawn rate* de **10/sec**, durée **60 secondes**.

4. Observez les métriques : RPS, taux d'erreurs HTTP, latences (p50, p95, p99).

> 💡 **Question 4** : Quelle stratégie affiche le meilleur RPS, taux d'erreurs HTTP, et latences? Observez-vous plus d'erreurs `409` qu'avec YugabyteDB? Pourquoi? Illustrez avec des captures d'écran de Locust.

### 4. Résilience du cluster et cohérence des données

CockroachDB garantit la cohérence via le protocole **Raft** : tant qu'une majorité de nœuds (*quorum*) est disponible, le cluster continue de fonctionner.

1. Lancez un test de charge en continu (**50 utilisateurs**, *spawn rate* **2/sec**, sans durée limite).

2. Arrêtez un nœud secondaire :
```bash
docker stop cockroach2
```

3. Observez si le taux d'erreur augmente dans Locust et combien de temps dure le basculement (*failover*).

4. Vérifiez le statut des nœuds via l'API :
```bash
curl http://localhost:5000/cluster/nodes
```

5. Redémarrez le nœud et observez la reprise :
```bash
docker start cockroach2
```

> 💡 **Question 5** : Est-ce que le taux d'erreur a augmenté lors de l'arrêt du nœud? Combien de temps a duré le basculement? Après le redémarrage de `cockroach2`, les données sont-elles cohérentes entre les nœuds? Comparez avec le comportement observé dans la version YugabyteDB.

## 📦 Livrables

- Un fichier `.zip` contenant l'intégralité du code source du projet Labo 09 (version CockroachDB).
- Un rapport en `.pdf` répondant aux questions présentées dans ce document. Il est obligatoire d'illustrer vos réponses avec du code ou des captures d'écran/terminal.

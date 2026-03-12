# Labo 09 – Bases de données distribuées et verrous distribués : YugabyteDB

<img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Ets_quebec_logo.png" width="250">

ÉTS - LOG430 - Architecture logicielle - Chargé de laboratoire : Gabriel C. Ullmann.

## 🎯 Objectifs d'apprentissage

- Comprendre le concept de **verrou distribué** (*distributed lock*) et pourquoi il est essentiel dans les systèmes distribués
- Observer comment YugabyteDB distribue les données entre plusieurs nœuds via le **sharding**
- Comparer les stratégies de verrouillage **pessimiste** et **optimiste** en termes de latence et de fiabilité
- Mesurer le comportement du système sous forte concurrence avec des tests de charge
- Vérifier la **résilience** et la **cohérence des données** lors d'une panne de nœud

## ⚙️ Setup

L'architecture de ce laboratoire repose sur un cluster YugabyteDB à trois nœuds (`yugabyte1`, `yugabyte2`, `yugabyte3`). Contrairement à une base de données classique centralisée, YugabyteDB distribue automatiquement les données et les transactions entre les nœuds, ce qui introduit de nouveaux défis liés à la **concurrence** et à la **cohérence**. Pour gérer ces défis, nous allons explorer deux stratégies de verrouillage qui permettent d'éviter que plusieurs transactions ne modifient les mêmes données simultanément de manière incohérente.

> 📝 **NOTE** : Dans une vraie application de production, les nœuds d'un cluster YugabyteDB seraient déployés sur des serveurs physiques distincts, voire dans des zones de disponibilité différentes. Par simplicité, dans ce labo, les trois nœuds tournent tous dans des conteneurs Docker sur la même machine.

### 1. Clonez le dépôt

Créez votre propre dépôt à partir du dépôt gabarit (template). Vous pouvez modifier la visibilité pour le rendre privé si vous le souhaitez.

```bash
git clone https://github.com/[votrenom]/log430-labo9
cd log430-labo9
```

### 2. Créez un fichier .env

Créez un fichier `.env` basé sur `.env.example` :

```sh
DB_HOST=yugabyte1
DB_PORT=5433
DB_NAME=yugabyte
DB_USER=yugabyte
DB_PASSWORD=yugabyte
```

### 3. Créez un réseau Docker

```bash
docker network create labo09-network
```

### 4. Préparez l'environnement de développement

Démarrez les conteneurs. Suivez les mêmes étapes que pour les derniers laboratoires.

```bash
docker compose build
docker compose up -d
```

> 📝 **NOTE** : Le conteneur `init-db` démarrera, initialisera la base de données, puis s'arrêtera automatiquement. Si vous remarquez qu'il est arrêté, c'est tout à fait normal.

## 🧪 Activités pratiques

### 1. Observer le schéma et le cluster

Commençons par explorer l'interface d'administration de YugabyteDB pour comprendre comment les données sont organisées et répliquées dans le cluster.

1. Ouvrez http://localhost:7000 (**YB Master UI**).

2. Observez la liste des nœuds et identifiez les rôles **leader** et **follower**. Dans une base de données distribuée, il y a toujours un nœud maître (*leader*) qui coordonne les décisions de consensus (quelles transactions sont validées, dans quel ordre) et plusieurs nœuds secondaires (*followers*) qui répliquent les données. Cette séparation garantit la cohérence même en cas de panne d'un nœud.

3. Cliquez sur **Tables > Orders** et observez les **tablets**. Un tablet est l'unité de base du sharding dans YugabyteDB : chaque table est découpée en plusieurs tablets, et chaque tablet est assigné à un nœud différent. Cela permet de distribuer la charge de lecture et d'écriture horizontalement. Pour en savoir plus, consultez la [documentation officielle sur le tablet splitting](https://docs.yugabyte.com/stable/architecture/docdb-sharding/tablet-splitting/).

4. Pour visualiser directement les données stockées, exécutez la commande suivante via l'onglet **Exec** de Docker Desktop sur le conteneur `yugabyte1`. Vous devriez voir une table vide :

```sh
ysqlsh -h yugabyte1 -U yugabyte -c "SELECT * FROM orders;"
```

Exécutez le test de concurrence suivant via l'onglet **Exec** de Docker Desktop. Ne vous inquiétez pas pour la compréhension approfondie de ce test, nous l'étudierons lors de la prochaine activité:

```bash
python tests/concurrency_test.py --threads 5 --product 3
```

Répetez la vérification. Vous devriez maintenant voir de nouveaux enregistrements :

```sh
ysqlsh -h yugabyte1 -U yugabyte -c "SELECT * FROM orders;"
```

> 💡 **Question 1** : Quelle est la sortie du terminal que vous obtenez? Si vous répétez cette commande sur `yugabyte2` et `yugabyte3`, est-ce que la sortie est identique? Illustrez votre réponse avec des captures d'écran du terminal.

### 2. Verrouillage pessimiste vs. optimiste

Dans un contexte de base de données distribuée, plusieurs instances de la base de données peuvent tenter de modifier les mêmes lignes au même moment. Sans mécanisme de contrôle, cela peut mener à des **conditions de course** (*race conditions*) : par exemple, deux transactions lisent un stock de 1 unité, toutes les deux décident de le décrémenter, et on se retrouve avec un stock négatif.

Dans ce laboratoire, nous étudierons deux approches pour éviter ce type de problème :

- **Verrouillage optimiste** : Chaque ligne de stock dans la table `stocks` possède une colonne `version`. Une transaction lit la version courante, calcule la nouvelle quantité, puis effectue un `UPDATE` uniquement si la version en base de données correspond toujours à celle qu'elle a lue. Si aucune ligne n'est affectée, c'est qu'une autre transaction a déjà modifié la ligne entre-temps. La transaction recommence alors depuis le début, jusqu'à un maximum de tentatives (`max_retries`). Cette approche évite les verrous lourds et est performante quand les conflits sont rares.

- **Verrouillage pessimiste** : La transaction acquiert un verrou au niveau de la ligne dès la lecture (`SELECT … FOR UPDATE`). Toute autre transaction qui tente de toucher la même ligne dans la table `stocks` sera **bloquée** jusqu'à ce que la première transaction soit terminée (commit ou rollback). Cette approche garantit qu'aucun conflit ne peut survenir, au prix d'une latence plus élevée en cas de forte contention.

Lisez le code dans `src/write_order.py` pour voir comment les deux approches sont implémentées dans ce projet. Pour comparer les deux approches en conditions réelles, exécutez le test de concurrence suivant via l'onglet **Exec** de Docker Desktop :

```bash
python tests/concurrency_test.py --threads 20 --product 3
```

L'article avec l'ID 3 a un stock initial de 2 unités. Avec 20 threads tentant simultanément de passer une commande d'une unité, seules 2 commandes devraient être acceptées. Si le système en accepte davantage, cela indique que le verrou ne fonctionne pas correctement.

Après l'exécution du test, vérifiez le stock final depuis votre machine hôte. Après le test, le stock de l'article ID 3 devrait être zero :

```bash
curl http://localhost:5000/stocks
```

> 💡 **Question 2** : Observez la latence moyenne des deux approches affichée dans la sortie du test. Laquelle a la latence la plus élevée et pourquoi? Illustrez votre réponse avec les sorties du terminal.

> 💡 **Question 3** : Répétez le test avec 5 threads au lieu de 20. Qui a actuellement la latence moyenne la plus élevée et pourquoi? Illustrez votre réponse avec les sorties du terminal.

### 3. Test de charge avec Locust

Maintenant que nous avons observé les deux stratégies en isolation, nous allons les comparer sous une charge soutenue afin de mesurer leur impact sur le débit (*throughput*) et le taux d'erreurs de l'application.

1. Réinitialisez les stocks avant de commencer depuis votre machine hôte :
```bash
curl -X POST http://localhost:5000/stocks/reset
```

2. Ouvrez l'interface Locust à l'adresse http://localhost:8089.

3. Configurez un test avec **50 utilisateurs**, un *spawn rate* de **10 utilisateurs/seconde**, et une durée de **60 secondes**.

4. Observez les métriques en temps réel : RPS (*requests per second*), taux d'erreurs HTTP, et latences (p50, p95, p99).

> 💡 **Question 4** : Quelle stratégie affiche le meilleur RPS, taux d'erreurs HTTP, et latences (p50, p95, p99)? Illustrez votre réponse avec des captures d'écran ou statistiques de l'interface Locust.

### 4. Résilience du cluster et cohérence des données

L'un des avantages majeurs d'une base de données distribuée comme YugabyteDB est sa capacité à continuer de fonctionner même en cas de panne d'un nœud, grâce à la réplication et au protocole de consensus Raft. Dans cette activité, nous allons vérifier ce comportement en simulant une panne pendant un test de charge.

1. Lancez un test de charge en continu depuis l'interface Locust (**50 utilisateurs**, un *spawn rate* de **2 utilisateurs/seconde**, sans durée limite).

2. Pendant que le test tourne, arrêtez un nœud secondaire :
```bash
docker stop yugabyte2
```

3. Observez dans Locust si le taux d'erreur augmente et, si oui, combien de temps dure la période de basculement (*failover*) avant que le système se stabilise.

4. Redémarrez le nœud arrêté et observez la reprise :
```bash
docker start yugabyte2
```

> 💡 **Question 5** : Est-ce que le taux d'erreur a augmenté lors de l'arrêt du nœud? Combien de temps a duré le basculement? Après le redémarrage de `yugabyte2`, les données sont-elles cohérentes entre les nœuds? Illustrez votre réponse avec des captures d'écran de Locust et du terminal.

## 📦 Livrables

- Un fichier `.zip` contenant l'intégralité du code source du projet Labo 09.
- Un rapport en `.pdf` répondant aux questions présentées dans ce document. Il est obligatoire d'illustrer vos réponses avec du code ou des captures d'écran/terminal.
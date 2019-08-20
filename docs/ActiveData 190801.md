
# ActiveData Capability Overview (August 2019)

With the spectre of ActiveData's retirement; maybe replaced with Google's Big Query: We will summarize ActiveData in terms of problems it solves and the  capabilities it provides. This can serve as a checklist for a successor.


## Problems

The problems we discuss are common in the data management space, and can be split into 3 major categories 



### Service

The data must be accessible, which means there is a machine that serves the data. This machine 


The problems relating to maintaining a service 

* Maintaining a data service is work
  * redundancy, 
  * backup and recovery, 
  * security updates, 
  * scaling
* Transactional systems can not answer big questions - Even if you have a data service they must work with other data services to be useful.  Consider  Bugzilla x Tasks x Alerts  - Copy the data in, or 
* Low query latency is work - The time between submitting the query and getting back an answer depends on the machine power and data locality and data structure
* Data Timeliness is work - any caching, or warehouse 

### Data

The shape of the data is important for manipulation. Organization of data is important for discovery. 

* Locating data; required data is sparse
  * Name
  * similar data
* Shape of the data; standard data
  * fields
  * relations to connected data
  * 
* Use cases driving data extraction APIs and declaring schema


Use-case driven analysis vs automated ingestion


### Analysis

* Large data extraction (data moved to code, which is wrong)
* Support complex queries - Analysis is hard; the data must go through verification, links to other data, transformed for presentation   
* Update and fix data
* Analytic Functions (window functions)



## Service Solution: Database as a Service!?

A database server solves many of these problems. Many micro-service candidates get built into a larger application because a database server solves many of the above problems

### More problems

* Query latency is high - 
* Queries take resources -  
* Queries consume resources, locking database from other transactions
* Human-managed schema
* SQL is not suited for simple queries
* SQL computationally unbounded (QoS) 


## Service Solution: ElasticSearch?

* A service *candidate*
* Document database is denormalized, is a hierarchical database
* Everything indexed - low query latency
* no loops, no joins, computationally bounded
* No locking transactional system
* Handle multitude of schemas from many sources
* scales to multiple machines
* recovery restoration
* automated schema management 
* offset query load from transactional systems


### Problems

* Service has zero security: Can not exposed to public 
* Separate service, ETL required
* Query language not suited for analysis
* Many machines is expensive
* OutOfMemory exceptions 


## Service Solution: ElasticSearch + ActiveData + ETL

* public gateway for ES
* simpler data model (shape reduces choices)
* simpler query language
* ETL ingestion from various sources
* SpotManager - Cheaper nodes, but diverse nodes cause shard balancing problems, Docker, but better 
* esShardBlancer - Balance shards according to machine capabilities
* Supervisor for OoM - but still have zombie nodes 


ETL is for decoupling from transactional systems and denormalizing the data








## Interlude: General Design Patterns

* bring code to data, not data to the code
* OLTP - fast update data
* OLAP - fast query data
* send queries to server, do not pull data to client


## Data Solution: Typed JSON

* Typed JSON

dynamic schema

all data is array data (logically, not in implementation)

json -> matrix  SIMD  

parallelism - threads, tasks (async), 


## Data Solution: Denormalization

* pre joined, no join costs at query time
* documents database is hierarchical database
* natural sharding 
* forced data shape, less options 
* reverse indexes
* MySQL_to_S3


denormalized is *smaller*


Many tests get run in one task

    |test.id| = number of records in test
    |test.name| = number of unique test names


    |task.id| = unique tasks
    |task.type| = 
    |task.timestamp| = timestamp




    |task.id|


    |test.id|*(sizeof(test.id)+sizeof(test.name))

    |     task.name| -> |task.id| => |task.id| -> |test.id| => |test.id| -> |test.name|

    |test.task.name| ->                           |test.id| => |test.id| -> |test.name|


## Data Solution: Safe Accessors  

* mo-dots - accessors "."

All values are array of values

| Encoding |  Logical |
|----------|----------|
|   null   |    []    |
|    x     |   [x]    |
|  [x, y]  |  [x, y]  |

 

## Data Solution: JSON Expressions

* code as data: stored in config files, communicated between applications
* code can build queries to offload work


## Data Solution: JSON Query Expressions

* dot-delimited paths to other tables - hierarchical database
* regular query language
* not SQL, use grids
* edges (SQL select by cube)


## Data Solution: Many Implementations

* jx-elasticsearch
* jx-python
* jx-sqlite




# Future Solutions

## Service Solution: BigQuery 

* is a 3rd party service
* centralized destination for data
* low query latency?
* offset query load from transactional systems
* standard query language
 

### Problems

* Human-managed schema (ActiveData?)
* SQL is not suited for queries over unclean data (ActiveData?)
* SQL Computationally unbounded (ActiveData?) 
* ETL ingestion from various sources (ActiveData?)




-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: dkh
-- ------------------------------------------------------
-- Server version	8.0.45-0ubuntu0.24.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `stock_history`
--

DROP TABLE IF EXISTS `stock_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stock_history` (
  `date` date NOT NULL COMMENT '交易所行情日期',
  `code` varchar(20) NOT NULL COMMENT '证券代码',
  `open` decimal(10,4) DEFAULT NULL COMMENT '开盘价',
  `high` decimal(10,4) DEFAULT NULL COMMENT '最高价',
  `low` decimal(10,4) DEFAULT NULL COMMENT '最低价',
  `close` decimal(10,4) DEFAULT NULL COMMENT '收盘价',
  `preclose` decimal(10,4) DEFAULT NULL COMMENT '前收盘价',
  `volume` bigint DEFAULT NULL COMMENT '成交数量（股）',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交金额（元）',
  `adjustflag` int DEFAULT NULL COMMENT '复权状态(1：后复权， 2：前复权，3：不复权)',
  `turn` decimal(10,6) DEFAULT NULL COMMENT '换手率',
  `tradestatus` int DEFAULT NULL COMMENT '交易状态(1：正常交易 0：停牌)',
  `pctChg` decimal(10,6) DEFAULT NULL COMMENT '涨跌幅(百分比)',
  `peTTM` decimal(10,4) DEFAULT NULL COMMENT '滚动市盈率',
  `pbMRQ` decimal(10,4) DEFAULT NULL COMMENT '市净率',
  `psTTM` decimal(10,4) DEFAULT NULL COMMENT '滚动市销率',
  `pcfNcfTTM` decimal(10,4) DEFAULT NULL COMMENT '滚动市现率',
  `isST` int DEFAULT NULL COMMENT '是否ST(1是，0否)',
  `rsi_14` decimal(10,4) DEFAULT NULL,
  `k_9_3` decimal(10,4) DEFAULT NULL,
  `d_9_3` decimal(10,4) DEFAULT NULL,
  `j_9_3` decimal(10,4) DEFAULT NULL,
  `macd_dif` decimal(10,4) DEFAULT NULL,
  `macd_dea` decimal(10,4) DEFAULT NULL,
  `macd_hist` decimal(10,4) DEFAULT NULL,
  PRIMARY KEY (`date`,`code`),
  KEY `idx_code` (`code`),
  KEY `idx_date` (`date`),
  KEY `idx_code_date` (`code`,`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-11 14:24:43

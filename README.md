# 医院 Oracle HIS ETL 最小闭环工具

这个项目用于第一阶段验证医院 HIS Oracle 数据库的数据管道闭环：

1. 测试 Oracle 连接；
2. 查询 HIS 基础表字段结构；
3. 按出院日期范围抽取患者基本信息；
4. 使用患者字段 `brxh` 关联抽取住院诊断；
5. 导出 CSV / Excel；
6. 生成抽取摘要；
7. 写入运行日志。

第一版只实现 HIS 患者基本信息表 `jk_wsb.brjbxx` 和住院诊断表 `jk_wsb.brzdqk`。LIS、RIS、病理、内镜、网页平台、CVAT、MinIO 等能力只做后续预留，不在本工具中实现。

## 目录结构

```text
hospital_data_etl/
  README.md
  requirements.txt
  .env.example
  config.example.yaml
  src/
    main.py
    config.py
    oracle_client.py
    validators.py
    extractors/
      his.py
      metadata.py
    exporters/
      csv_exporter.py
      excel_exporter.py
    utils/
      logger.py
      masking.py
  sql/
    his/
      brjbxx_columns.sql
      brzdqk_columns.sql
      extract_patients.sql
      extract_diagnosis.sql
  outputs/
  logs/
```

## 环境安装

建议使用 Python 3.10 或更新版本。

```bash
cd hospital_data_etl
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

本项目优先使用 `oracledb` thin mode，不要求安装 Oracle Instant Client。若遇到旧版 Oracle 报错 `DPY-3010`，可切换到 thick mode，并安装 Oracle Instant Client。

## 配置 .env

复制示例文件：

```bash
copy .env.example .env
```

按实际只读账号修改 `.env`：

```env
HIS_HOST=192.168.0.65
HIS_PORT=1521
HIS_SERVICE_NAME=orcl
HIS_USERNAME=jk_wsb
HIS_PASSWORD=please_change_me

OUTPUT_DIR=outputs
LOG_DIR=logs
```

如需更多结构化配置，可复制 `config.example.yaml` 为 `config.yaml`。`config.yaml` 支持 `${HIS_HOST}` 这类环境变量占位。

## 测试连接

```bash
python -m src.main test-connection --source his
```

成功时会在控制台和 `logs/etl_YYYYMMDD.log` 中记录连接成功。日志不会输出密码。

常见失败原因：

- `HIS_PASSWORD` 未配置；
- 未执行 `pip install -r requirements.txt`；
- 数据库地址、端口、service name 错误；
- 当前机器不在数据库允许访问的内网；
- 账号没有连接权限；
- 旧版 Oracle 不支持 thin mode，需要设置 `ORACLE_CLIENT_MODE=thick`。

## 字段摸底

```bash
python -m src.main inspect-his
```

输出文件：

- `outputs/brjbxx_columns_YYYYMMDD_HHMMSS.csv`
- `outputs/brzdqk_columns_YYYYMMDD_HHMMSS.csv`
- `outputs/his_columns_YYYYMMDD_HHMMSS.xlsx`

字段结构 SQL 位于：

- `sql/his/brjbxx_columns.sql`
- `sql/his/brzdqk_columns.sql`

## 患者 + 诊断抽取

```bash
python -m src.main extract-his --start-date 20240301 --end-date 20240303
```

日期格式必须是 `YYYYMMDD`。抽取逻辑按患者出院日期字段 `cyrq` 过滤，诊断表通过 `brxh` 关联患者范围。

输出文件：

- `outputs/patients_20240301_20240303.csv`
- `outputs/diagnosis_20240301_20240303.csv`
- `outputs/his_patient_diagnosis_20240301_20240303.xlsx`
- `outputs/summary_20240301_20240303.json`

`summary_*.json` 包含：

- `start_date`
- `end_date`
- `patient_count`
- `diagnosis_count`
- `unique_brxh_count`
- `has_patient_diagnosis_link`

## 输出说明

CSV 默认使用 `utf-8-sig`，方便 Excel 打开中文。Excel 文件包含对应 sheet：

- 字段摸底：`brjbxx_columns`、`brzdqk_columns`
- 患者诊断抽取：`patients`、`diagnosis`、`summary`

第一版导出保留 HIS 原始字段，不随意改字段名。`src/utils/masking.py` 提供姓名、身份证号、手机号的基础脱敏函数，但默认不修改导出结果，便于做字段确认和闭环验证。

## 常见问题

### 是否需要 Oracle Instant Client？

通常不需要。`oracledb` 默认 thin mode 可直接连接 Oracle。只有遇到特殊认证、加密或老版本数据库兼容问题时，才可能需要 thick mode 和 Oracle Instant Client。


### 旧版 Oracle / DPY-3010

如果测试连接时报错 `DPY-3010: connections to this database server version are not supported by python-oracledb in thin mode`，说明目标 Oracle 版本不支持 thin mode。处理方式：

1. 安装与操作系统匹配的 Oracle Instant Client。
2. 在 `.env` 中设置：

```env
ORACLE_CLIENT_MODE=thick
ORACLE_CLIENT_LIB_DIR=C:\path\to\instantclient_19_XX
```

Windows 下 `ORACLE_CLIENT_LIB_DIR` 指向包含 `oci.dll` 的目录；Linux 下目录中应包含 `libclntsh.so`，并且需要在 Python 启动前配置 `LD_LIBRARY_PATH`。
Linux/WSL 下如果 Instant Client 放在项目目录，可使用项目提供的启动脚本，它会在 Python 启动前设置 `LD_LIBRARY_PATH`：

```bash
bash run_linux.sh test-connection --source his
bash run_linux.sh inspect-his
bash run_linux.sh extract-his --start-date 20240301 --end-date 20240303
```

也可以手动执行：

```bash
export LD_LIBRARY_PATH="$PWD/instantclient-basic-linux.x64-23.26.2.0.0/instantclient_23_26:$LD_LIBRARY_PATH"
python -m src.main test-connection --source his
```
### 为什么没有真实数据库也能提交代码？

本工具把连接、SQL、参数、导出、日志和异常处理都封装完整。没有数据库时无法完成真实抽取，但运行命令会给出清晰错误提示，代码结构仍可审查和交接。

### 能否把 `.env` 提交到 Git？

不能。`.env` 和 `config.yaml` 已加入 `.gitignore`，只能提交 `.env.example` 和 `config.example.yaml`。

### 日志里会不会写入患者隐私？

CLI 只记录连接状态、抽取日期、行数、输出文件路径和错误摘要，不打印患者整行数据，不打印身份证号、姓名等敏感字段。

## 数据安全注意事项

1. 该工具只应使用只读数据库账号。
2. 数据库账号密码不得提交到 Git。
3. `.env` 必须加入 `.gitignore`，本项目已默认配置。
4. 导出的患者数据可能包含姓名、身份证号、联系方式、住院号、诊断等敏感信息，只能在内网和授权目录下使用。
5. 第一版导出保留原始字段，仅用于字段确认和数据闭环验证。
6. 正式科研数据集必须做脱敏、访问控制、审批留痕和最小必要字段管理。




## RIS 对接摸底

RIS 第一版只做连接验证、权限验证和元数据摸底，不做复杂清洗，不批量导出患者隐私数据。

### RIS 配置

在 `.env` 中配置 RIS 账号和连接信息：

```env
RIS_DB_USER=实际账号
RIS_DB_PASSWORD=please_change_me
RIS_DB_HOST=192.168.211.87
RIS_DB_PORT=1521
RIS_DB_SERVICE_NAME=ris
ORACLE_CLIENT_MODE=thick
ORACLE_CLIENT_LIB_DIR=/home/ps/project/hospital_data_etl/instantclient-basic-linux.x64-23.26.2.0.0/instantclient_23_26
```

Linux 下 thick mode 需要在启动 Python 前设置动态库路径：

```bash
export ORACLE_CLIENT_LIB_DIR=/home/ps/project/hospital_data_etl/instantclient-basic-linux.x64-23.26.2.0.0/instantclient_23_26
export LD_LIBRARY_PATH=$ORACLE_CLIENT_LIB_DIR:$LD_LIBRARY_PATH
```

也可以使用项目里的 `run_linux.sh`，它会先设置 `LD_LIBRARY_PATH`：

```bash
bash run_linux.sh test-connection --source ris
```

### RIS 命令

测试 RIS 连接：

```bash
python -m src.main test-connection --source ris
```

列出 RIS 当前账号可访问的业务表，默认最多 100 行，并导出 `outputs/ris_tables.csv`：

```bash
python -m src.main list-tables --source ris --limit 50
```

搜索疑似 RIS 业务字段，默认最多 200 行，并导出 `outputs/ris_columns_candidates.csv`：

```bash
python -m src.main search-columns --source ris --limit 200
```

查看指定表结构，并导出 `outputs/ris_OWNER_TABLE_schema.csv`：

```bash
python -m src.main inspect-schema --source ris --owner OWNER --table TABLE_NAME
```

### 常见 RIS 错误

- `DPI-1047`：Oracle Instant Client 未加载，检查 `ORACLE_CLIENT_LIB_DIR` 和 `LD_LIBRARY_PATH`。
- `DPY-3010`：thin mode 不支持旧版 Oracle，需要使用 thick mode。
- `ORA-01017`：账号或密码错误。
- `ORA-01031`：账号权限不足。
- `ORA-00604`：数据库登录触发器或递归 SQL 报错。
- `ORA-12170`：网络或防火墙导致连接超时。
- `ORA-12514` / `ORA-12541`：service_name 或 listener 问题。

### 需要医院信息科确认

1. RIS 查询账号是否已经开通。
2. 是否允许来源 IP `172.51.99.121` 登录 RIS。
3. RIS 检查申请表名称。
4. RIS 检查报告表名称。
5. 患者标识字段，例如 `brxh`、住院号、门诊号。
6. 检查类型、检查部位、检查名称字段。
7. 报告文本、影像印象、报告时间字段。
8. 是否有影像文件路径或 DICOM 接口。

## 多数据源配置

当前支持的数据源：

- `his`：兼容别名，等同于 `his1`。
- `his1`：程序默认 HIS 数据源，`192.168.0.65:1521/orcl`。
- `his1r`：HIS 查询库 / 运维连接 / 字段摸底数据源，`192.168.220.10:15065/orcl`。
- `lis`：LIS 检验查询库，`192.168.211.85:1521/lisdb`。
- `ris`：RIS 影像检查查询库，已保留前期摸底命令。

`.env` 示例：

```env
HIS1_HOST=192.168.0.65
HIS1_PORT=1521
HIS1_SERVICE_NAME=orcl
HIS1_USERNAME=jk_wsb
HIS1_PASSWORD=please_change_me

HIS1R_HOST=192.168.220.10
HIS1R_PORT=15065
HIS1R_SERVICE_NAME=orcl
HIS1R_USERNAME=jk_wsb
HIS1R_PASSWORD=please_change_me

LIS_HOST=192.168.211.85
LIS_PORT=1521
LIS_SERVICE_NAME=lisdb
LIS_USERNAME=please_change_me
LIS_PASSWORD=please_change_me
```

为兼容旧版本，`his` 默认映射到 `his1`；如果没有配置 `HIS1_*`，程序会回退读取旧的 `HIS_*`。

## 多数据源连接测试

```bash
python -m src.main test-connection --source his
python -m src.main test-connection --source his1
python -m src.main test-connection --source his1r
python -m src.main test-connection --source lis
```

连接测试会执行 `select 1 as ok from dual`，日志显示 source、host、port、service_name 和 username，不输出密码。连接成功会生成不含密码的 `outputs/connection_SOURCE_YYYYMMDD_HHMMSS.json`。

## HIS1r 用途说明

HIS1r 主要用于查询库、运维连接、权限验证和字段摸底。正式程序抽取默认仍使用 HIS1。

字段摸底：

```bash
python -m src.main inspect-his --source his1
python -m src.main inspect-his --source his1r
```

从 HIS1r 抽取患者和诊断必须显式指定 `--source his1r`，并确认信息科授权：

```bash
python -m src.main extract-his --source his1r --start-date 20240301 --end-date 20240303 --force
```

HIS 抽取默认不允许超过 31 天，超过必须加 `--force`。

## LIS 摸底流程

第一版不写死 LIS 业务表名，只做结构发现和小样例验证。

推荐流程：

1. 配置 `LIS_USERNAME` / `LIS_PASSWORD`。
2. 运行连接测试：

```bash
python -m src.main test-connection --source lis
```

3. 运行自动发现：

```bash
python -m src.main discover-lis
```

输出：

- `outputs/lis_owners_YYYYMMDD_HHMMSS.csv`
- `outputs/lis_accessible_tables_YYYYMMDD_HHMMSS.csv`
- `outputs/lis_candidate_tables_YYYYMMDD_HHMMSS.csv`
- `outputs/lis_candidate_columns_YYYYMMDD_HHMMSS.csv`
- `outputs/lis_discovery_YYYYMMDD_HHMMSS.xlsx`

4. 根据 Excel 找到疑似检验申请表、报告表、结果明细表。
5. 对候选表运行指定表摸底：

```bash
python -m src.main inspect-lis-table --owner LIS_OWNER --table TABLE_NAME --sample-limit 10
```

输出：

- `outputs/lis_OWNER_TABLE_columns_YYYYMMDD_HHMMSS.csv`
- `outputs/lis_OWNER_TABLE_sample_YYYYMMDD_HHMMSS.csv`
- `outputs/lis_OWNER_TABLE_inspect_YYYYMMDD_HHMMSS.xlsx`

6. 人工确认患者标识、检验项目、结果、单位、参考范围、异常标志、采样时间、报告时间等字段。
7. 第二阶段再实现正式 LIS 检验结果抽取。

## LIS/HIS 样例数据安全

导出的 LIS/HIS 样例数据可能包含患者姓名、身份证号、手机号、住院号、门诊号、检验结果等敏感信息。

- 只能在内网授权目录使用。
- 不要上传到公网。
- 不要提交到 Git。
- 不要在日志或聊天窗口粘贴整行患者数据。
- 正式科研数据集必须做脱敏、权限控制和审计。


## RIS_DIMAGE 影像路径导出

`JK_WSB.RIS_DIMAGE` 是 RIS 影像路径表/视图，第一版只导出路径相关字段，不导出患者姓名、身份证、电话、地址等隐私字段。

```bash
python -m src.main export-ris-dimage --limit 1000 --output outputs/ris_dimage_sample.csv
```

输出 CSV 使用 `utf-8-sig` 编码，表头为：

```text
影像记录ID,影像序列号,存储根路径,详细路径,图像文件名,完整影像路径
```

`完整影像路径` 由 `STOREPATH`、`PATHDETAIL`、`IMAGEF` 拼接生成，仅用于查看；原始字段不会被修改。命令必须指定行数限制或使用默认 `--limit 1000`，不会无条件全表导出。

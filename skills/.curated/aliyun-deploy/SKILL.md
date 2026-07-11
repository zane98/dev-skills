---
name: aliyun-deploy
description: 阿里云 ECS 容器部署与排障。用于用户要求在阿里云发布、回滚或诊断应用，包括本地构建镜像、SSH 上传、远端 Docker Compose、迁移和健康检查；不用于其他云平台或普通本地开发。
---

# 阿里云部署

## 与其他 skill 的关系

- 部署中需要修改应用代码、配置或迁移时，使用 `$development` 按改动加载领域 reference，验证完成后再继续部署。
- 涉及复杂迁移、生产拓扑或分阶段发布时，使用 `$development-plan` 明确顺序、观测和恢复路径。
- 部署请求不自动授权 commit、PR/MR 合并或与目标环境无关的仓库清理。

## 默认原则

- 先读项目自己的部署文件，再决定动作。
- 默认只有一个 production 目标，不拆 test / staging / release。
- 业务镜像在本地构建，上传到阿里云 ECS 后再 `docker load`。
- 远端只负责迁移、`docker compose up -d`、健康检查和回滚。
- 密钥、数据库密码、OSS 凭证只放远端 env 或密钥管理，不进仓库。

## 先确认

如果目标信息不全，先拿齐这几项：

- 主机 IP 或 SSH Host alias
- SSH 用户
- SSH 私钥路径
- 远端部署目录
- 远端 env 文件路径
- 访问域名或站点地址

## 标准流程

1. `git status --short --branch`
2. 读取项目的部署脚本和 compose 文件
3. 本地构建 amd64 Docker 镜像
4. 打包并通过 SSH 传到 ECS
5. 远端 `docker load`
6. 执行数据库迁移
7. `docker compose up -d`
8. 检查 `/health`、`/api/health` 或项目约定的健康接口
9. 记录镜像 tag、Git SHA、时间和目标主机

## 排障与回滚

- 先看 `docker ps`、`docker logs`、远端 manifest。
- 一次只用一个 SSH 连接，别并发把小机器摇晕。
- 回滚优先切回上一版镜像 tag，再 `docker compose up -d`。
- 如果迁移已执行，不盲目 downgrade，优先做向前兼容修复。

## 阿里云相关口径

- ECS 负责运行容器。
- OSS 放对象存储凭证和文件材料。
- RDS / 云数据库 放业务数据。
- Redis 可本地容器或托管服务，按项目口径选择。

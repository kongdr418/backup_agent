# Docker 部署

## 环境变量

默认不要求准备 `.env` 文件。前端设置页可以直接填写各家模型的 API Key，容器空环境也能启动。

如果你想让后端提供服务端兜底 Key，可以在 `docker-compose.yml` 的 `backend.environment` 里按需添加 `MINIMAX_API_KEY`、`DEEPSEEK_API_KEY`、`XFYUN_API_KEY`、`MIMO_API_KEY` 等。

## 启动

```bash
docker compose up --build
```

访问：

- 前端：http://localhost:5173
- 后端：http://localhost:5000

## 校验

```bash
docker compose config
docker compose build
```

如果本机没有 Docker CLI，可以先在宿主机运行：

```bash
python3 -m compileall backend/app.py
cd frontend && npm run build
```

## 数据持久化

`docker-compose.yml` 会把这些目录挂载到容器中，容器重建后数据仍保留：

- `backend/memory`
- `backend/generated_svg_ppt`
- `backend/generators/generated_*`

## 说明

微课视频板块已移除，因此镜像不再安装 LibreOffice、Poppler、ffmpeg、ffprobe。

如果 PPT 或课堂内容里需要更完整的字体效果，可以在 `backend/Dockerfile` 里继续补充字体包。

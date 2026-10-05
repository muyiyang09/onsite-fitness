# 上门体育 · 管理端 PC

Vue 3 + Element Plus + Vite，运营后台，对接后端 `http://localhost:8080`。

## 功能

- **教练审核**：待审核教练列表，通过/驳回
- **课程管理**：课程增删改查、起售/停售
- **订单管理**：按订单号/手机号/状态查询、订单详情

## 运行

```bash
cd admin-web
npm install
npm run dev
```

浏览器打开 http://localhost:5173 ，默认账号 `admin / 123456`。

## 说明

- Vite 代理已把 `/admin` 请求转发到 `http://localhost:8080`（无需后端配 CORS）。
- 后端需先启动（`platform-backend/backend-server` 下 `mvn spring-boot:run`）。
- 教练审核是 MVP 关键闭环：新教练入驻后（status=0 待审核），需在此审核通过才能接单。

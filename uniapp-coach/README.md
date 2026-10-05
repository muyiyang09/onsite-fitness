# 上门体育 · 教练端（uniapp）

上门私教平台教练端小程序，Vue 2 + uniapp，对接后端 `http://localhost:8080`。与用户端 `uniapp-user` 同骨架。

## 页面（8 个）

| 页面 | 路径 | 说明 |
|---|---|---|
| 工作台 | pages/index | 教练资料 + 待办入口 |
| 登录 | pages/login | 手机号 + 密码登录 |
| 入驻 | pages/register | 教练入驻（资质） |
| 订单列表 | pages/order | 待接单/待服务/服务中/已完成 |
| 订单详情 | pages/order/detail | 接单/拒单/开始/完成服务 |
| 派单池 | pages/pool | 抢单 |
| 排期 | pages/schedule | 生成/查看排期 |
| 我的 | pages/my | 资料 + 评价 + 退出 |

## 运行步骤

1. HBuilderX 导入本目录。
2. 后端先启动（`backend-server` 下 `mvn spring-boot:run`，需 MySQL/Redis）。
3. `api/request.js` 的 `BASE_URL` 默认 `http://localhost:8080`。
4. 配置 `manifest.json` 的 mp-weixin appid。
5. 运行到微信开发者工具。

## 关键约定

- 教练端 token 头名为 `token`（对应后端 `coach-token-name`）。
- 登录后 `coach_id` 存本地，订单接单/抢单/服务接口以 `coachId` 参数传。
- 入驻后需平台审核（`coach.status` 0→1）才能接单；种子教练「李教练 13900000001 / 123456」已审核通过可直接登录测试。

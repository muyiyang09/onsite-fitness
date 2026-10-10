# 上门体育 · 用户端（uniapp）

上门私教平台用户端小程序，Vue 2 + uniapp，对接后端 `http://localhost:8080`。

## 页面（10 个）

| 页面 | 路径 | 说明 |
|---|---|---|
| 首页 | pages/index | 分类 + 课程浏览 |
| 教练列表 | pages/coach | 教练列表 + 就近派单入口 |
| 教练详情 | pages/coach/detail | 教练信息 + 排期时段选择 |
| 预约下单 | pages/booking | 指定教练/派单两种模式 + 时段 + 地址 + 模拟支付 |
| 订单列表 | pages/order | 按状态筛选 |
| 订单详情 | pages/order/detail | 详情 + 取消/支付/评价 |
| 评价 | pages/review | 教练 + 课程双维度评分 |
| 地址列表 | pages/address | 增删改、设默认、选地址 |
| 地址编辑 | pages/address/edit | 地址表单 |
| 我的 | pages/my | 微信登录 + 入口 |

## 运行步骤

1. 用 **HBuilderX** 导入本目录（或 `uni-app` CLI）。
2. 后端先启动：在 `platform-backend/backend-server` 下 `mvn spring-boot:run`（需 MySQL/Redis 已启动、已导入 `sql/onsite_fitness.sql`）。
3. 改后端地址：`api/request.js` 的 `BASE_URL`（默认 `http://localhost:8080`）。
4. 配置微信 appid：`manifest.json` → `mp-weixin.appid`（真机/微信预览需要）。
5. 运行到微信开发者工具。

## 已知依赖

- **微信登录**需要真实 appid/secret：前端 `manifest.json` 配 appid，后端 `application-dev.yml` 配 `onsite.wx.app-id/app-secret`。无 appid 时登录会失败（其余浏览/下单接口需先登录拿 token）。
- 后端 token 头名为 `authentication`（见 `api/request.js`）。
- MVP 用**模拟支付**：`PUT /user/order/payment` 直接改订单状态，无真实微信支付。

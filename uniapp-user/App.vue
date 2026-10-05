<script>
export default {
    onLaunch: function() {
        console.log('上门体育用户端启动');
    },
    onShow: function() {},
    onHide: function() {}
};
</script>

<style>
/* ===== 设计令牌：健康绿 · 柔和中性 ===== */
page {
    --accent: #00B578;
    --accent-soft: #E6F7F0;
    --bg: #F6F7F9;
    --card: #FFFFFF;
    --text-1: #1A1D21;
    --text-2: #6B7280;
    --text-3: #9CA3AF;
    --line: #EEF0F3;

    background-color: var(--bg);
    font-size: 28rpx;
    color: var(--text-1);
    font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', sans-serif;
}

/* ===== 共享组件样式 ===== */
/* 卡片：统一圆角 + 柔和着色阴影 */
.card {
    background: var(--card);
    border-radius: 24rpx;
    padding: 28rpx;
    box-shadow: 0 2rpx 16rpx rgba(17, 24, 39, 0.05);
}

/* 标签 */
.tag {
    display: inline-block;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 20rpx;
    padding: 6rpx 16rpx;
    border-radius: 8rpx;
}

/* 主按钮：全圆角 */
.btn-primary {
    background: var(--accent);
    color: #FFFFFF;
    border-radius: 999rpx;
    font-weight: 600;
}

.btn-primary.btn-disabled {
    background: #D1D5DB;
}

/* 价格 */
.price {
    color: #FF6B35;
    font-weight: 600;
}

/* 文字截断 */
.text-overflow {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ===== 空状态 ===== */
.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 100rpx 40rpx;
    color: var(--text-3);
}
.empty-icon {
    font-size: 88rpx;
    margin-bottom: 24rpx;
    opacity: 0.8;
}
.empty-text {
    font-size: 26rpx;
}
.empty-sub {
    font-size: 22rpx;
    color: #C0C4CC;
    margin-top: 8rpx;
}
</style>

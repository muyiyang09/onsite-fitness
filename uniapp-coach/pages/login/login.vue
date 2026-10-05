<template>
    <view class="page">
        <view class="logo">
            <view class="logo-icon">🏋️</view>
            <text class="logo-title">上门体育 · 教练端</text>
            <text class="logo-sub">上门私教，接单赚钱</text>
        </view>

        <view class="form card">
            <view class="form-item">
                <input class="input" v-model="phone" type="number" placeholder="请输入手机号" />
            </view>
            <view class="form-item no-border">
                <input class="input" v-model="password" password placeholder="请输入密码" />
            </view>
        </view>

        <button class="login-btn" :class="{ 'btn-disabled': submitting }" :disabled="submitting" @tap="doLogin">
            {{ submitting ? '登录中...' : '登录' }}
        </button>

        <view class="register-link" @tap="goRegister">还没有账号？立即入驻 ›</view>
    </view>
</template>

<script>
const api = require('../../api/index.js');
const { TOKEN_KEY, COACH_ID_KEY } = require('../../api/request.js');

export default {
    data() {
        return {
            phone: '',
            password: '',
            submitting: false
        };
    },
    methods: {
        async doLogin() {
            if (!this.phone || !this.password) {
                uni.showToast({ title: '请输入手机号和密码', icon: 'none' });
                return;
            }
            this.submitting = true;
            try {
                const data = await api.login(this.phone, this.password);
                uni.setStorageSync(TOKEN_KEY, data.token);
                uni.setStorageSync(COACH_ID_KEY, data.id);
                uni.setStorageSync('coach_info', { id: data.id, name: data.name, phone: data.phone });
                uni.showToast({ title: '登录成功', icon: 'success' });
                setTimeout(() => {
                    uni.switchTab({ url: '/pages/index/index' });
                }, 500);
            } catch (e) {
                this.submitting = false;
            }
        },
        goRegister() {
            uni.navigateTo({ url: '/pages/register/register' });
        }
    }
};
</script>

<style>
.page {
    padding: 100rpx 40rpx;
}
.logo {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 60rpx;
}
.logo-icon {
    font-size: 80rpx;
    margin-bottom: 20rpx;
}
.logo-title {
    font-size: 42rpx;
    font-weight: 700;
    color: #2F80ED;
}
.logo-sub {
    font-size: 26rpx;
    color: #9CA3AF;
    margin-top: 12rpx;
}
.form {
    padding: 0 32rpx;
    margin-bottom: 40rpx;
}
.form-item {
    padding: 32rpx 0;
    border-bottom: 1rpx solid #EEF0F3;
}
.form-item.no-border {
    border-bottom: none;
}
.input {
    font-size: 30rpx;
}
.login-btn {
    background: #2F80ED;
    color: #fff;
    font-size: 32rpx;
    border-radius: 999rpx;
    line-height: 88rpx;
    font-weight: 600;
}
.register-link {
    text-align: center;
    color: #2F80ED;
    font-size: 26rpx;
    margin-top: 30rpx;
}
</style>

<template>
    <div class="login-wrap">
        <el-card class="login-card">
            <h2 class="title">上门体育 · 管理端</h2>
            <el-form @submit.prevent>
                <el-form-item>
                    <el-input v-model="username" placeholder="账号" size="large" />
                </el-form-item>
                <el-form-item>
                    <el-input v-model="password" type="password" placeholder="密码" size="large" show-password @keyup.enter="doLogin" />
                </el-form-item>
                <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="doLogin">登录</el-button>
            </el-form>
            <p class="tip">默认账号 admin / 123456</p>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const router = useRouter();
const auth = useAuthStore();

const username = ref('admin');
const password = ref('123456');
const loading = ref(false);

async function doLogin() {
    if (!username.value || !password.value) {
        ElMessage.warning('请输入账号和密码');
        return;
    }
    loading.value = true;
    try {
        const data = await api.post('/admin/employee/login', {
            username: username.value,
            password: password.value
        });
        auth.login(data.token);
        ElMessage.success('登录成功');
        router.push('/');
    } catch (e) {
        ElMessage.error((e as Error).message || '登录失败');
    } finally {
        loading.value = false;
    }
}
</script>

<style scoped>
.login-wrap {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #1c4a8a, #2f80ed);
}
.login-card {
    width: 360px;
}
.title {
    text-align: center;
    margin-bottom: 24px;
}
.tip {
    text-align: center;
    color: #999;
    font-size: 12px;
    margin-top: 16px;
}
</style>

<template>
    <el-container class="layout">
        <el-aside width="200px" class="aside">
            <div class="logo">上门体育 · 管理端</div>
            <el-menu
                :default-active="$route.path"
                background-color="#001529"
                text-color="#c0c4cc"
                active-text-color="#409eff"
                router
            >
                <el-menu-item index="/coach">教练审核</el-menu-item>
                <el-menu-item index="/course">课程管理</el-menu-item>
                <el-menu-item index="/order">订单管理</el-menu-item>
                <el-menu-item index="/dispatchPool">派单池监控</el-menu-item>
            </el-menu>
            <div class="logout" @click="logout">退出登录</div>
        </el-aside>

        <el-main class="main">
            <router-view />
        </el-main>
    </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const router = useRouter();
const auth = useAuthStore();

function logout() {
    auth.logout();
    router.push('/login');
}
</script>

<style scoped>
.layout {
    height: 100%;
}
.aside {
    background: #001529;
    display: flex;
    flex-direction: column;
}
.logo {
    color: #fff;
    font-size: 16px;
    font-weight: bold;
    padding: 20px 16px;
    text-align: center;
}
.el-menu {
    border-right: none;
    flex: 1;
}
.logout {
    color: #c0c4cc;
    text-align: center;
    padding: 16px;
    cursor: pointer;
    font-size: 14px;
}
.main {
    background: #f0f2f5;
    padding: 20px;
}
</style>

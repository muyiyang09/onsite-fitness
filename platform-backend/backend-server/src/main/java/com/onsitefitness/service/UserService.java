package com.onsitefitness.service;

import com.onsitefitness.dto.UserLoginDTO;
import com.onsitefitness.entity.User;

public interface UserService {
    User wxLogin(UserLoginDTO userLoginDTO);

    /**
     * 开发环境 mock 登录（跳过微信 code2session，按手机号直接登录/注册）
     * @param phone 手机号
     * @return 用户
     */
    User mockLogin(String phone);
}

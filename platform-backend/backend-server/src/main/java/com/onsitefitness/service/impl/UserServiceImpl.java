package com.onsitefitness.service.impl;

import com.alibaba.fastjson2.JSONObject;
import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.dto.UserLoginDTO;
import com.onsitefitness.entity.User;
import com.onsitefitness.exception.LoginFailedException;
import com.onsitefitness.mapper.UserMapper;
import com.onsitefitness.properties.JwtProperties;
import com.onsitefitness.properties.WeChatProperties;
import com.onsitefitness.service.UserService;
import com.onsitefitness.utils.HttpClientUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@Service
public class UserServiceImpl implements UserService {
    @Autowired
    private UserMapper userMapper;
    public static final String WX_LOGIN = "https://api.weixin.qq.com/sns/jscode2session?";
    @Autowired
    private WeChatProperties weChatProperties;
    @Autowired
    private JwtProperties jwtProperties;
    @Override
    public User wxLogin(UserLoginDTO userLoginDTO) {
        // 调用微信接口服务，获取当前用户的openid
        String openid = getOpenId(userLoginDTO.getCode());
        // 判断openid是否存在
        if(openid == null){
            throw new LoginFailedException(MessageConstant.LOGIN_FAILED);
        }
        //判断当前用户是否为新用户
        User user = userMapper.getByOpenId(openid);

        //如果是新用户，自动注册
        if(user == null){
            user = User.builder()
                    .openid(openid)
                    .createTime(LocalDateTime.now())
                    .build();
            userMapper.insert(user);
        }
        //返回用户对象
        return user;
    }

    @Override
    public User mockLogin(String phone) {
        if (phone == null || phone.trim().isEmpty()) {
            phone = "13800138000";
        }
        String openid = "mock_" + phone;
        // 判断是否已存在
        User user = userMapper.getByOpenId(openid);
        // 新用户自动注册
        if (user == null) {
            user = User.builder()
                    .openid(openid)
                    .name("测试用户" + phone)
                    .phone(phone)
                    .createTime(LocalDateTime.now())
                    .build();
            userMapper.insert(user);
        }
        return user;
    }

    /**
     * 获取微信用户的openid
     * @param code 微信登录返回的code
     * @return  openid
     */
    public String getOpenId(String code) {
        // 调用微信接口服务，获取当前用户的openid
        Map<String, String> map = new HashMap<>();
        map.put("appid", weChatProperties.getAppid());
        map.put("secret", weChatProperties.getSecret());
        map.put("js_code", code);
        map.put("grant_type", "authorization_code");
        String json = HttpClientUtil.doGet(WX_LOGIN, map);

        JSONObject jsonObject = JSONObject.parseObject(json);
        String openid = jsonObject.getString("openid");
        return openid;
    }
}

package com.onsitefitness.controller.user;

import com.onsitefitness.constant.JwtClaimsConstant;
import com.onsitefitness.dto.UserLoginDTO;
import com.onsitefitness.entity.User;
import com.onsitefitness.properties.JwtProperties;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.UserService;
import com.onsitefitness.service.TokenBlacklistService;
import com.onsitefitness.utils.JwtUtil;
import com.onsitefitness.vo.UserLoginVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/user/user")
@Tag(name = "C端用户相关接口")
@Slf4j
public class UserController {
    @Autowired
    private UserService userService;
    @Autowired
    private JwtProperties jwtProperties;
    @Autowired
    private TokenBlacklistService tokenBlacklistService;

    /**
     * 微信登录
     * @param userLoginDTO
     * @return
     */
    @PostMapping("/login")
    @Operation(summary = "微信登录")
    public Result<UserLoginVO> login(@RequestBody UserLoginDTO userLoginDTO) {
        log.info("微信登录:{}", userLoginDTO.getCode());
        User user = userService.wxLogin(userLoginDTO);
        //微信用户登录成功后，生成token
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.USER_ID, user.getId());
        JwtUtil.JwtTokenResult tokenResult = JwtUtil.createJWT(
                jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);

        tokenBlacklistService.registerUserToken(
                String.valueOf(user.getId()),
                tokenResult.getJti(),
                jwtProperties.getUserTtl());

        UserLoginVO userLoginVO = UserLoginVO.builder()
                .id(user.getId())
                .openid(user.getOpenid())
                .token(tokenResult.getToken())
                .build();
        return Result.success(userLoginVO);
    }

    /**
     * 开发环境 mock 登录（跳过微信 code2session）
     * @param body {"phone": "13800138000"}
     * @return
     */
    @PostMapping("/mockLogin")
    @Profile("!prod")
    @Operation(summary = "mock登录(开发用)")
    public Result<UserLoginVO> mockLogin(@RequestBody Map<String, String> body) {
        String phone = body.get("phone");
        log.info("mock登录:{}", phone);
        User user = userService.mockLogin(phone);
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.USER_ID, user.getId());
        JwtUtil.JwtTokenResult tokenResult = JwtUtil.createJWT(
                jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);

        tokenBlacklistService.registerUserToken(
                String.valueOf(user.getId()),
                tokenResult.getJti(),
                jwtProperties.getUserTtl());

        UserLoginVO userLoginVO = UserLoginVO.builder()
                .id(user.getId())
                .openid(user.getOpenid())
                .token(tokenResult.getToken())
                .build();
        return Result.success(userLoginVO);
    }
}

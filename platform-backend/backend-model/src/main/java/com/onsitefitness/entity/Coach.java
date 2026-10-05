package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 教练
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Coach implements Serializable {

    /**
     * 状态 0待审核 1已审(正常) 2驳回(禁用)
     */
    public static final Integer STATUS_PENDING = 0;
    public static final Integer STATUS_APPROVED = 1;
    public static final Integer STATUS_REJECTED = 2;

    private static final long serialVersionUID = 1L;

    private Long id;

    //教练端微信唯一标识
    private String openid;

    //姓名
    private String name;

    //手机号
    private String phone;

    //登录密码
    private String password;

    //性别 0 女 1 男
    private String sex;

    //头像
    private String avatar;

    //身份证号
    private String idNumber;

    //等级 1初级 2中级 3高级 4金牌
    private Integer level;

    //综合评分
    private BigDecimal rating;

    //服务半径(公里)
    private BigDecimal serviceRadiusKm;

    //服务城市区划编号
    private String cityCode;

    //服务城市名称
    private String cityName;

    //简介/擅长
    private String bio;

    //状态 0待审核 1正常 2禁用
    private Integer status;

    //入驻时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;

    //创建人
    private Long createUser;

    //修改人
    private Long updateUser;
}

package com.onsitefitness.dto;

import com.onsitefitness.entity.CoachCertificate;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.List;

/**
 * 教练入驻 DTO
 */
@Data
public class CoachRegisterDTO implements Serializable {

    private String name;

    private String phone;

    private String password;

    //性别 0女 1男
    private String sex;

    private String avatar;

    //身份证号
    private String idNumber;

    //等级 1初级 2中级 3高级 4金牌
    private Integer level;

    //服务半径(公里)
    private BigDecimal serviceRadiusKm;

    //服务城市编码
    private String cityCode;

    //服务城市名称
    private String cityName;

    //简介/擅长
    private String bio;

    //资质证书列表
    private List<CoachCertificate> certificates;

}

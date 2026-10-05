package com.onsitefitness.vo;

import com.onsitefitness.entity.CoachCertificate;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 教练 VO(含资质证书列表)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CoachVO implements Serializable {

    private Long id;

    private String openid;

    private String name;

    private String phone;

    private String sex;

    private String avatar;

    private String idNumber;

    private Integer level;

    private BigDecimal rating;

    private BigDecimal serviceRadiusKm;

    private String cityCode;

    private String cityName;

    private String bio;

    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    //资质证书列表
    private List<CoachCertificate> certificates;

}

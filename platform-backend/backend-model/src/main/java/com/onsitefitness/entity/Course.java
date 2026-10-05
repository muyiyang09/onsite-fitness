package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 课程（含规格字段，原 DishFlavor 已并入此表）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Course implements Serializable {

    private static final long serialVersionUID = 1L;

    private Long id;

    //课程名称
    private String name;

    //分类id
    private Long categoryId;

    //单次价格(元)
    private BigDecimal price;

    //封面图
    private String image;

    //课程描述
    private String description;

    //状态 0停售 1起售
    private Integer status;

    //强度（轻/中/高）
    private String intensity;

    //时长(分钟)
    private Integer durationMin;

    //适合人群
    private String suitCrowd;

    //所需器械(逗号分隔)
    private String equipment;

    //创建时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;

    //创建人
    private Long createUser;

    //修改人
    private Long updateUser;
}

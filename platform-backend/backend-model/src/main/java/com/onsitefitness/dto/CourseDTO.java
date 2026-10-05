package com.onsitefitness.dto;

import lombok.Data;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * 课程 DTO（课程规格字段已并入 course 表，无独立规格子表）
 */
@Data
public class CourseDTO implements Serializable {

    private Long id;
    //课程名称
    private String name;
    //课程分类id
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

}

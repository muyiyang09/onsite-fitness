package com.onsitefitness.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CourseVO implements Serializable {

    private Long id;
    //课程名称
    private String name;
    //课程分类id
    private Long categoryId;
    //单次价格
    private BigDecimal price;
    //封面图
    private String image;
    //课程描述
    private String description;
    //0 停售 1 起售
    private Integer status;
    //强度（轻/中/高）
    private String intensity;
    //时长(分钟)
    private Integer durationMin;
    //适合人群
    private String suitCrowd;
    //所需器械
    private String equipment;
    //更新时间
    private LocalDateTime updateTime;
    //分类名称
    private String categoryName;

}

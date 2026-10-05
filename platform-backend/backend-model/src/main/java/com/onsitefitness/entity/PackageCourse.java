package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 套餐课程关联
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PackageCourse implements Serializable {

    private static final long serialVersionUID = 1L;

    private Long id;

    //套餐id
    private Long packageId;

    //课程id
    private Long courseId;

    //套餐内该课程节数
    private Integer courseNum;

    //创建时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;
}

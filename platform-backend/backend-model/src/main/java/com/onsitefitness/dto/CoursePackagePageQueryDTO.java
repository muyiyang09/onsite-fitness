package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

@Data
public class CoursePackagePageQueryDTO implements Serializable {

    private int page;

    private int pageSize;

    private String name;

    //分类id
    private Long categoryId;

}

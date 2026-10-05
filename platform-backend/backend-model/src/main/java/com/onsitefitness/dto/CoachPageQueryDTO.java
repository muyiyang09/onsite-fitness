package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 教练分页查询 DTO
 */
@Data
public class CoachPageQueryDTO implements Serializable {

    private int page;

    private int pageSize;

    private String name;

    private String phone;

    //状态 0待审核 1已审 2驳回
    private Integer status;

}

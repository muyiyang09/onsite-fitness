package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 评价分页查询 DTO(按教练)
 */
@Data
public class OrderReviewPageQueryDTO implements Serializable {

    private int page;

    private int pageSize;

    private Long coachId;

}

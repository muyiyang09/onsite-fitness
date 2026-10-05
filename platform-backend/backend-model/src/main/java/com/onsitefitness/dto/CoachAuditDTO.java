package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 教练审核 DTO
 */
@Data
public class CoachAuditDTO implements Serializable {

    private Long coachId;

    //审核状态 1通过 2驳回
    private Integer status;

    //驳回原因
    private String rejectReason;

    //审核人
    private Long auditUser;

}

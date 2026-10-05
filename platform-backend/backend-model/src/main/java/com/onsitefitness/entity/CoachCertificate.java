package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 教练资质/证书
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CoachCertificate implements Serializable {

    /**
     * 审核状态 0待审核 1通过 2驳回
     */
    public static final Integer STATUS_PENDING = 0;
    public static final Integer STATUS_APPROVED = 1;
    public static final Integer STATUS_REJECTED = 2;

    private static final long serialVersionUID = 1L;

    private Long id;

    //教练id
    private Long coachId;

    //证书类型（国职/ACE/NASM/NSCA等）
    private String certType;

    //证书编号
    private String certNo;

    //证书图片
    private String imageUrl;

    //审核状态 0待审核 1通过 2驳回
    private Integer status;

    //驳回原因
    private String rejectReason;

    //上传时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;

    //审核人
    private Long auditUser;

    //审核时间
    private LocalDateTime auditTime;
}

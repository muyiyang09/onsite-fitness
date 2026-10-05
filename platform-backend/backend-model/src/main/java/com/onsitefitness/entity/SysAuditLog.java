package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 业务审计日志实体（§6.28）：记录敏感业务动作（下单/抢单/退款/处理退款/教练审核）。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SysAuditLog implements Serializable {

    private static final long serialVersionUID = 1L;

    private Long id;

    /** 操作人id */
    private Long userId;

    /** 动作类型：order.submit / order.seize / order.refund / order.handle / coachAudit */
    private String type;

    /** 业务主键id（订单id / 教练id 等） */
    private Long bizId;

    /** 操作描述 */
    private String detail;

    /** 扩展信息（JSON，如失败原因） */
    private String jsonExtra;

    /** 创建时间 */
    private LocalDateTime createdAt;
}

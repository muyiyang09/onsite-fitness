package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 派单/抢单池（合并表，用 dispatch_type 区分）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DispatchPool implements Serializable {

    /**
     * 派单类型 0待派 1系统派 2教练抢单
     */
    public static final Integer DISPATCH_PENDING = 0;
    public static final Integer DISPATCH_SYSTEM = 1;
    public static final Integer DISPATCH_SEIZE = 2;

    /**
     * 状态 0待派 1已派 2已取消
     */
    public static final Integer STATUS_PENDING = 0;
    public static final Integer STATUS_DISPATCHED = 1;
    public static final Integer STATUS_CANCELLED = 2;

    private static final long serialVersionUID = 1L;

    private Long id;

    //订单id
    private Long orderId;

    //最终派给/抢到的教练
    private Long coachId;

    //派单类型 0待派 1系统派 2教练抢单
    private Integer dispatchType;

    //状态 0待派 1已派 2已取消
    private Integer status;

    //服务城市编码(同城就近派单)
    private String cityCode;

    //派单超时时间(兜底取消)
    private LocalDateTime expireTime;

    //进入派单池时间
    private LocalDateTime createTime;

    //派单完成时间
    private LocalDateTime dispatchTime;
}

package com.onsitefitness.vo;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 派单池可抢列表VO(教练端)
 */
@Data
public class DispatchPoolVO implements Serializable {

    private static final long serialVersionUID = 1L;

    //派单池id
    private Long id;

    //订单id
    private Long orderId;

    //服务城市编码
    private String cityCode;

    //派单超时时间
    private LocalDateTime expireTime;

    //进入派单池时间
    private LocalDateTime createTime;

    //上门日期
    private LocalDate scheduleDate;

    //上门时段
    private String timeSlot;

    //上门详细地址
    private String address;

    //联系人
    private String consignee;

    //手机号
    private String phone;

    //订单金额
    private BigDecimal amount;

    // === 管理端监控字段 ===

    //派单池状态 0待派 1已派 2已取消
    private Integer status;

    //派单类型 0待派 1系统派 2教练抢单
    private Integer dispatchType;

    //最终派给/抢到的教练
    private Long coachId;

    //派单完成时间
    private LocalDateTime dispatchTime;

    //订单号
    private String orderNumber;
}

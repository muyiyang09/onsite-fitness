package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 预约订单
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Orders implements Serializable {

    /**
     * 订单状态 1待付款 2待接单 3待服务 4服务中 5已完成 6已取消 7拒单
     */
    public static final Integer PENDING_PAYMENT = 1;
    public static final Integer TO_BE_ACCEPTED = 2;
    public static final Integer TO_BE_SERVED = 3;
    public static final Integer IN_SERVICE = 4;
    public static final Integer COMPLETED = 5;
    public static final Integer CANCELLED = 6;
    public static final Integer REJECTED = 7;

    /**
     * 订单状态 8退款中 9已退款 10已评价
     */
    public static final Integer REFUNDING = 8;
    public static final Integer REFUNDED = 9;
    public static final Integer REVIEWED = 10;

    /**
     * 下单模式 1指定教练 2派单池
     */
    public static final Integer MODE_APPOINT = 1;
    public static final Integer MODE_DISPATCH = 2;

    /**
     * 派单类型(派单池订单) 0待派 1系统派 2教练抢单
     */
    public static final Integer DISPATCH_PENDING = 0;
    public static final Integer DISPATCH_SYSTEM = 1;
    public static final Integer DISPATCH_SEIZE = 2;

    /**
     * 支付状态 0未支付 1已支付
     */
    public static final Integer UN_PAID = 0;
    public static final Integer PAID = 1;

    private static final long serialVersionUID = 1L;

    private Long id;

    //订单号
    private String orderNumber;

    //订单状态
    private Integer status;

    //下单用户id
    private Long userId;

    //教练id（指定单下单时填 / 派单成功后回填）
    private Long coachId;

    //上门地址id
    private Long addressBookId;

    //下单模式 1指定教练 2派单池
    private Integer orderMode;

    //派单类型(派单池订单) 0待派 1系统派 2教练抢单
    private Integer dispatchType;

    //预约排期id
    private Long scheduleId;

    //上门日期
    private LocalDate scheduleDate;

    //上门时段(如 09:00-10:00)
    private String timeSlot;

    //联系人
    private String consignee;

    //手机号
    private String phone;

    //性别
    private String sex;

    //上门详细地址
    private String address;

    //实收金额
    private BigDecimal amount;

    //支付方式 1微信 2支付宝
    private Integer payMethod;

    //支付状态 0未支付 1已支付
    private Integer payStatus;

    //下单时间
    private LocalDateTime submitTime;

    //支付时间
    private LocalDateTime checkoutTime;

    //教练接单时间
    private LocalDateTime acceptTime;

    //服务开始时间
    private LocalDateTime serviceStartTime;

    //服务完成时间
    private LocalDateTime serviceEndTime;

    //取消时间
    private LocalDateTime cancelTime;

    //取消原因
    private String cancelReason;

    //拒单原因
    private String rejectionReason;

    //用户备注
    private String remark;

    //训练记录(JSON)
    private String trainRecord;

    //体测数据(JSON)
    private String bodyData;

    //创建时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;
}

package com.onsitefitness.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.onsitefitness.entity.OrderDetail;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@Data
public class OrdersSubmitDTO implements Serializable {

    //地址簿id
    private Long addressBookId;

    //付款方式 1微信 2支付宝
    private Integer payMethod;

    //备注
    private String remark;

    //总金额
    private BigDecimal amount;

    //下单模式 1指定教练 2派单池
    private Integer orderMode;

    //派单类型(派单池订单) 0待派 1系统派 2教练抢单
    private Integer dispatchType;

    //预约排期id
    private Long scheduleId;

    //上门日期
    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate scheduleDate;

    //上门时段(如 09:00-10:00)
    private String timeSlot;

    //教练id(指定教练下单时填)
    private Long coachId;

    //订单明细列表(课程/套餐明细)
    private List<OrderDetail> orderDetails;
}

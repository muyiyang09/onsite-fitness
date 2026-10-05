package com.onsitefitness.vo;

import com.onsitefitness.entity.DispatchPool;
import com.onsitefitness.entity.OrderDetail;
import com.onsitefitness.entity.Orders;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.io.Serializable;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class OrderVO extends Orders implements Serializable {

    //订单课程信息
    private String orderDishes;

    //订单详情
    private List<OrderDetail> orderDetailList;

    //派单池信息(派单池订单时返回)
    private DispatchPool dispatchPool;

}

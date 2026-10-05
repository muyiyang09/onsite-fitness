package com.onsitefitness.mapper;
import com.github.pagehelper.Page;
import com.onsitefitness.dto.GoodsSalesDTO;
import com.onsitefitness.dto.OrdersPageQueryDTO;
import com.onsitefitness.entity.Orders;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface OrderMapper {
    /**
     * 新增订单
     * @param orders
     */
    void insert(Orders orders);

    /**
     * 根据订单号查询订单
     * @param orderNumber
     */
    @Select("select * from orders where order_number = #{orderNumber}")
    Orders getByNumber(String orderNumber);

    /**
     * 修改订单信息
     * @param orders
     */
    void update(Orders orders);

    Page<Orders> pageQuery(OrdersPageQueryDTO ordersPageQueryDTO);

    /**
     * 根据id查询订单
     * @param id
     */
    @Select("select * from orders where id=#{id}")
    Orders getById(Long id);

    /**
     * 根据订单状态查询订单数量
     */
    @Select("select count(id) from orders where status = #{status}")
    Integer countStatus(Integer status);

    /**
     * 根据订单状态和下单时间查询订单
     */
    @Select("select * from orders where status = #{status} and submit_time < #{submitTime}")
    List<Orders> getByStatusAndSubmitTime(Integer status, LocalDateTime submitTime);

    /**
     * 根据订单状态和支付状态查询订单
     */
    Double sumByMap(Map map);

    Integer countByMap(Map map);

    List<GoodsSalesDTO> getSalesTop(LocalDateTime begin, LocalDateTime end);
}

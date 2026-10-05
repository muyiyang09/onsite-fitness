package com.onsitefitness.mapper;

import com.onsitefitness.entity.DispatchPool;
import com.onsitefitness.vo.DispatchPoolVO;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface DispatchPoolMapper {

    /**
     * 新增派单池记录
     * @param dispatchPool
     */
    @Insert("insert into dispatch_pool (order_id, coach_id, dispatch_type, status, city_code, expire_time, create_time, dispatch_time) " +
            "values (#{orderId}, #{coachId}, #{dispatchType}, #{status}, #{cityCode}, #{expireTime}, #{createTime}, #{dispatchTime})")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    void insert(DispatchPool dispatchPool);

    /**
     * 根据id查询
     */
    @Select("select * from dispatch_pool where id = #{id}")
    DispatchPool getById(Long id);

    /**
     * 根据订单id查询
     */
    @Select("select * from dispatch_pool where order_id = #{orderId}")
    DispatchPool getByOrderId(Long orderId);

    /**
     * 修改派单池(抢单: status=DISPATCHED, coach_id, dispatch_type=SEIZE, dispatch_time)
     * @param dispatchPool
     */
    void update(DispatchPool dispatchPool);

    /**
     * 抢单乐观锁更新: status=PENDING -> DISPATCHED
     * 返回影响行数(0 表示抢单失败)
     */
    @Update("update dispatch_pool set status = #{status}, coach_id = #{coachId}, dispatch_type = #{dispatchType}, dispatch_time = #{dispatchTime} " +
            "where id = #{id} and status = #{pendingStatus}")
    int seize(@Param("id") Long id, @Param("status") Integer status, @Param("coachId") Long coachId,
              @Param("dispatchType") Integer dispatchType, @Param("dispatchTime") java.time.LocalDateTime dispatchTime,
              @Param("pendingStatus") Integer pendingStatus);

    /**
     * 派单池可抢列表(教练端按城市)
     */
    List<DispatchPoolVO> listSeizableByCityCode(@Param("cityCode") String cityCode, @Param("statusPending") Integer statusPending);

    /**
     * 管理端：查询全部派单池记录（可按状态/城市筛选）
     */
    List<DispatchPoolVO> listAllForAdmin(@Param("status") Integer status, @Param("cityCode") String cityCode);

    /**
     * 查询超时未派单的记录(status=PENDING 且 expire_time<NOW())
     */
    @Select("select * from dispatch_pool where status = #{status} and expire_time < now()")
    List<DispatchPool> listExpired(@Param("status") Integer status);
}

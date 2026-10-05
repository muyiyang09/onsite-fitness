package com.onsitefitness.mapper;

import com.onsitefitness.entity.CoachSchedule;
import com.onsitefitness.vo.CoachScheduleVO;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface CoachScheduleMapper {

    /**
     * 根据id查询排期
     */
    @Select("select * from coach_schedule where id = #{id}")
    CoachSchedule getById(Long id);

    /**
     * 锁定排期(乐观锁): status=AVAILABLE -> OCCUPIED, 绑定订单id
     * 返回影响行数(0 表示排期已被占,锁定失败)
     */
    @Update("update coach_schedule set status = #{toStatus}, order_id = #{orderId} " +
            "where id = #{id} and status = #{fromStatus}")
    int lockSchedule(@Param("id") Long id, @Param("orderId") Long orderId,
                    @Param("fromStatus") Integer fromStatus, @Param("toStatus") Integer toStatus);

    /**
     * 释放排期: status -> AVAILABLE, order_id = null
     * 返回影响行数
     */
    @Update("update coach_schedule set status = #{toStatus}, order_id = null where id = #{id}")
    int releaseSchedule(@Param("id") Long id, @Param("toStatus") Integer toStatus);

    /**
     * 按 coachId+date+slot 查重(防重复生成)
     */
    @Select("select count(id) from coach_schedule where coach_id = #{coachId} " +
            "and schedule_date = #{scheduleDate} and time_slot = #{timeSlot}")
    int countByCoachDateSlot(@Param("coachId") Long coachId,
                             @Param("scheduleDate") LocalDate scheduleDate,
                             @Param("timeSlot") String timeSlot);

    /**
     * 批量新增排期
     * @param schedules
     */
    void insertBatch(List<CoachSchedule> schedules);

    /**
     * 教练查询自己某日期区间的排期
     */
    List<CoachScheduleVO> listByCoachAndDateRange(@Param("coachId") Long coachId,
                                                  @Param("startDate") LocalDate startDate,
                                                  @Param("endDate") LocalDate endDate);

    /**
     * 用户端查询教练某日可约排期(status=AVAILABLE)
     */
    List<CoachScheduleVO> listAvailableByCoachAndDate(@Param("coachId") Long coachId,
                                                     @Param("scheduleDate") LocalDate scheduleDate);

}

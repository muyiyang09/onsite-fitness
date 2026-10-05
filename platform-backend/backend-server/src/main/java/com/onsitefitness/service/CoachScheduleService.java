package com.onsitefitness.service;

import com.onsitefitness.dto.CoachScheduleGenerateDTO;
import com.onsitefitness.vo.CoachScheduleVO;

import java.time.LocalDate;
import java.util.List;

public interface CoachScheduleService {

    /**
     * 生成排期(日期区间 x 时段,去重)
     * @param coachScheduleGenerateDTO
     */
    void generateSchedule(CoachScheduleGenerateDTO coachScheduleGenerateDTO);

    /**
     * 教练查询自己某日期区间的排期
     * @param coachId
     * @param startDate
     * @param endDate
     * @return
     */
    List<CoachScheduleVO> listByCoachAndDateRange(Long coachId, LocalDate startDate, LocalDate endDate);

    /**
     * 用户端查询教练某日可约排期
     * @param coachId
     * @param scheduleDate
     * @return
     */
    List<CoachScheduleVO> listAvailableByCoachAndDate(Long coachId, LocalDate scheduleDate);

}

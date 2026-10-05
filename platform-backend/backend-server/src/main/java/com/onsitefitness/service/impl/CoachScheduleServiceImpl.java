package com.onsitefitness.service.impl;

import com.onsitefitness.dto.CoachScheduleGenerateDTO;
import com.onsitefitness.entity.CoachSchedule;
import com.onsitefitness.mapper.CoachScheduleMapper;
import com.onsitefitness.service.CoachScheduleService;
import com.onsitefitness.vo.CoachScheduleVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Service
public class CoachScheduleServiceImpl implements CoachScheduleService {

    @Autowired
    private CoachScheduleMapper coachScheduleMapper;

    /**
     * 生成排期: 日期区间每个日期 x 每个时段, 按 coachId+date+slot 去重
     */
    @Override
    @Transactional
    public void generateSchedule(CoachScheduleGenerateDTO dto) {
        LocalDate start = dto.getStartDate();
        LocalDate end = dto.getEndDate();
        List<String> timeSlots = dto.getTimeSlots();
        if (start == null || end == null || timeSlots == null || timeSlots.isEmpty()) {
            return;
        }

        List<CoachSchedule> toInsert = new ArrayList<>();
        LocalDateTime now = LocalDateTime.now();
        for (LocalDate date = start; !date.isAfter(end); date = date.plusDays(1)) {
            for (String slot : timeSlots) {
                //查重防重复
                int cnt = coachScheduleMapper.countByCoachDateSlot(dto.getCoachId(), date, slot);
                if (cnt == 0) {
                    toInsert.add(CoachSchedule.builder()
                            .coachId(dto.getCoachId())
                            .scheduleDate(date)
                            .timeSlot(slot)
                            .status(CoachSchedule.STATUS_AVAILABLE)
                            .orderId(null)
                            .createTime(now)
                            .updateTime(now)
                            .build());
                }
            }
        }
        if (!toInsert.isEmpty()) {
            coachScheduleMapper.insertBatch(toInsert);
        }
    }

    /**
     * 教练查询自己某日期区间的排期
     */
    @Override
    public List<CoachScheduleVO> listByCoachAndDateRange(Long coachId, LocalDate startDate, LocalDate endDate) {
        return coachScheduleMapper.listByCoachAndDateRange(coachId, startDate, endDate);
    }

    /**
     * 用户端查询教练某日可约排期
     */
    @Override
    public List<CoachScheduleVO> listAvailableByCoachAndDate(Long coachId, LocalDate scheduleDate) {
        return coachScheduleMapper.listAvailableByCoachAndDate(coachId, scheduleDate);
    }
}

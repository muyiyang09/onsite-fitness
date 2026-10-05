package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDate;
import java.util.List;

/**
 * 教练排期生成 DTO
 */
@Data
public class CoachScheduleGenerateDTO implements Serializable {

    private Long coachId;

    //起始日期
    private LocalDate startDate;

    //结束日期
    private LocalDate endDate;

    //时段列表(如 09:00-10:00)
    private List<String> timeSlots;

}

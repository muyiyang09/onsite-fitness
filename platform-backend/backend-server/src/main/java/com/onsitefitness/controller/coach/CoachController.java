package com.onsitefitness.controller.coach;

import com.onsitefitness.context.BaseContext;
import com.onsitefitness.dto.CoachLoginDTO;
import com.onsitefitness.dto.CoachRegisterDTO;
import com.onsitefitness.dto.CoachScheduleGenerateDTO;
import com.onsitefitness.entity.Coach;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.CoachScheduleService;
import com.onsitefitness.service.CoachService;
import com.onsitefitness.vo.CoachLoginVO;
import com.onsitefitness.vo.CoachScheduleVO;
import com.onsitefitness.vo.CoachVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

/**
 * 教练端教练资料/登录/排期接口
 */
@RestController("coachCoachController")
@RequestMapping("/coach")
@Tag(name = "教练端教练资料与排期接口")
@Slf4j
public class CoachController {

    @Autowired
    private CoachService coachService;
    @Autowired
    private CoachScheduleService coachScheduleService;

    /**
     * 教练入驻
     */
    @PostMapping("/coach/register")
    @Operation(summary = "教练入驻")
    public Result<Long> register(@RequestBody CoachRegisterDTO coachRegisterDTO) {
        log.info("教练入驻：{}", coachRegisterDTO);
        Long coachId = coachService.register(coachRegisterDTO);
        return Result.success(coachId);
    }

    /**
     * 教练登录
     */
    @PostMapping("/coach/login")
    @Operation(summary = "教练登录")
    public Result<CoachLoginVO> login(@RequestBody CoachLoginDTO coachLoginDTO) {
        log.info("教练登录：{}", coachLoginDTO.getPhone());
        CoachLoginVO coachLoginVO = coachService.login(coachLoginDTO);
        return Result.success(coachLoginVO);
    }

    /**
     * 查询我的资料(coachId 从 BaseContext 取)
     */
    @GetMapping("/coach")
    @Operation(summary = "查询我的资料")
    public Result<CoachVO> myProfile() {
        Long coachId = BaseContext.getCurrentId();
        log.info("查询教练资料：coachId={}", coachId);
        CoachVO coachVO = coachService.getById(coachId);
        return Result.success(coachVO);
    }

    /**
     * 更新我的资料(仅可编辑字段)
     */
    @PutMapping("/coach")
    @Operation(summary = "更新我的资料")
    public Result updateProfile(@RequestBody Coach coach) {
        coach.setId(BaseContext.getCurrentId());
        log.info("更新教练资料：coachId={}", coach.getId());
        coachService.updateProfile(coach);
        return Result.success();
    }

    /**
     * 生成排期(coachId 以登录教练为准)
     */
    @PostMapping("/schedule/generate")
    @Operation(summary = "生成排期")
    public Result generateSchedule(@RequestBody CoachScheduleGenerateDTO dto) {
        log.info("生成排期：{}", dto);
        dto.setCoachId(BaseContext.getCurrentId());
        coachScheduleService.generateSchedule(dto);
        return Result.success();
    }

    /**
     * 查询我的排期(按日期区间)
     */
    @GetMapping("/schedule")
    @Operation(summary = "查询我的排期")
    public Result<List<CoachScheduleVO>> mySchedule(
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate endDate) {
        Long coachId = BaseContext.getCurrentId();
        log.info("查询教练排期：coachId={}, startDate={}, endDate={}", coachId, startDate, endDate);
        List<CoachScheduleVO> list = coachScheduleService.listByCoachAndDateRange(coachId, startDate, endDate);
        return Result.success(list);
    }
}

package com.onsitefitness.controller.user;

import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.CoachScheduleService;
import com.onsitefitness.service.CoachService;
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
 * 用户端教练浏览
 */
@RestController("userCoachController")
@RequestMapping("/user/coach")
@Tag(name = "C端-教练浏览接口")
@Slf4j
public class CoachController {

    @Autowired
    private CoachService coachService;
    @Autowired
    private CoachScheduleService coachScheduleService;

    /**
     * 按城市查询已审教练
     */
    @GetMapping("/list")
    @Operation(summary = "按城市查询已审教练")
    public Result<PageResult> list(String cityCode, int page, int pageSize) {
        log.info("按城市查询已审教练：cityCode={}, page={}, pageSize={}", cityCode, page, pageSize);
        PageResult pageResult = coachService.listByCity(cityCode, page, pageSize);
        return Result.success(pageResult);
    }

    /**
     * 根据id查询教练(含资质证书)
     */
    @GetMapping("/{id}")
    @Operation(summary = "根据id查询教练")
    public Result<CoachVO> getById(@PathVariable Long id) {
        log.info("根据id查询教练：{}", id);
        CoachVO coachVO = coachService.getById(id);
        coachVO.setIdNumber(null); // 用户端不返回身份证号
        return Result.success(coachVO);
    }

    /**
     * 查询教练某日可约排期
     */
    @GetMapping("/{coachId}/schedule")
    @Operation(summary = "查询教练某日可约排期")
    public Result<List<CoachScheduleVO>> availableSchedule(@PathVariable Long coachId,
                                                           @RequestParam @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate date) {
        log.info("查询教练可约排期：coachId={}, date={}", coachId, date);
        List<CoachScheduleVO> list = coachScheduleService.listAvailableByCoachAndDate(coachId, date);
        return Result.success(list);
    }
}

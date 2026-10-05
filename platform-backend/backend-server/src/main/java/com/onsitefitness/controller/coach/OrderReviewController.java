package com.onsitefitness.controller.coach;

import com.onsitefitness.context.BaseContext;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.OrderReviewService;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 教练端评价查看
 */
@RestController("coachOrderReviewController")
@RequestMapping("/coach/review")
@Tag(name = "教练端评价查看接口")
@Slf4j
public class OrderReviewController {

    @Autowired
    private OrderReviewService orderReviewService;

    /**
     * 分页查询当前教练收到的评价
     */
    @GetMapping("/page")
    @Operation(summary = "分页查询当前教练收到的评价")
    public Result<PageResult> page(int page, int pageSize) {
        Long coachId = BaseContext.getCurrentId();
        log.info("教练查询评价：coachId={}, page={}, pageSize={}", coachId, page, pageSize);
        PageResult pageResult = orderReviewService.pageQueryByCoach(coachId, page, pageSize);
        return Result.success(pageResult);
    }
}

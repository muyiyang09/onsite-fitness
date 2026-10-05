package com.onsitefitness.controller.admin;

import com.onsitefitness.result.Result;
import com.onsitefitness.service.ReportService;
import com.onsitefitness.vo.OrderReportVO;
import com.onsitefitness.vo.SalesTop10ReportVO;
import com.onsitefitness.vo.TurnoverReportVO;
import com.onsitefitness.vo.UserReportVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletResponse;
import java.time.LocalDate;

@RestController
@RequestMapping("/admin/report")
@Tag(name = "数据统计相关接口")
@Slf4j
public class ReportController {
    @Autowired
    private ReportService reportService;

    /**
     * 营业额统计
     * @param begin
     * @param end
     * @return
     */
    @GetMapping("/turnoverStatistics")
    @Operation(summary = "营业额统计")
    public Result<TurnoverReportVO> turnoverStatistics(
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate begin,
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate end) {
        log.info("营业额统计，开始日期：{}，结束日期：{}", begin, end);
        return Result.success(reportService.getTurnoverReport(begin, end));
    }

    /**
     * 用户统计
     * @param begin
     * @param end
     * @return
     */
    @GetMapping("/userStatistics")
    @Operation(summary = "用户统计")
    public Result<UserReportVO> userStatistics(
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate begin,
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate end) {
        log.info("用户统计，开始日期：{}，结束日期：{}", begin, end);
        return Result.success(reportService.getUserReport(begin, end));
    }

    /**
     * 订单统计
     * @param begin
     * @param end
     * @return
     */
    @GetMapping("/ordersStatistics")
    @Operation(summary = "订单统计")
    public Result<OrderReportVO> ordersStatistics(
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate begin,
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate end
    ){
        log.info("订单统计，开始日期：{}，结束日期：{}", begin, end);
        return Result.success(reportService.getOrderReport(begin, end));
    }

    /**
     * 销量排名top10
     * @param begin
     * @param end
     * @return
     */
    @GetMapping("/top10")
    @Operation(summary = "销量排名top10")
    public Result<SalesTop10ReportVO> salesTop10Statistics(
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate begin,
            @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate end
    ){
        log.info("销量排名top10，开始日期：{}，结束日期：{}", begin, end);
        return Result.success(reportService.getSalesTop10Report(begin, end));
    }

    /**
     * 导出报表
     * @param response
     */
    @GetMapping("/export")
    @Operation(summary = "导出运营数据报表")
    public void export(HttpServletResponse response) {  //response为HttpServletResponse对象,用于 设置响应头信息，实现文件下载
        // TODO: 导出报表
        log.info("导出报表");
        reportService.exportBusinessData(response);
    }

}

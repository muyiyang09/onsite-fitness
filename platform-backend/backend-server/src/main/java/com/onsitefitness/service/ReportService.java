package com.onsitefitness.service;

import com.onsitefitness.vo.OrderReportVO;
import com.onsitefitness.vo.SalesTop10ReportVO;
import com.onsitefitness.vo.TurnoverReportVO;
import com.onsitefitness.vo.UserReportVO;

import jakarta.servlet.http.HttpServletResponse;
import java.time.LocalDate;

public interface ReportService {
    TurnoverReportVO getTurnoverReport(LocalDate begin, LocalDate end);

    UserReportVO getUserReport(LocalDate begin, LocalDate end);

    OrderReportVO getOrderReport(LocalDate begin, LocalDate end);

    SalesTop10ReportVO getSalesTop10Report(LocalDate begin, LocalDate end);

    void exportBusinessData(HttpServletResponse response);
}

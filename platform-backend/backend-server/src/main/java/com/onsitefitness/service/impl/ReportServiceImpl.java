package com.onsitefitness.service.impl;

import com.onsitefitness.dto.GoodsSalesDTO;
import com.onsitefitness.entity.Orders;
import com.onsitefitness.mapper.OrderMapper;
import com.onsitefitness.mapper.UserMapper;
import com.onsitefitness.service.ReportService;
import com.onsitefitness.service.WorkspaceService;
import com.onsitefitness.vo.*;
import org.apache.commons.lang3.StringUtils;
import org.apache.poi.xssf.usermodel.XSSFRow;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import jakarta.servlet.ServletOutputStream;
import jakarta.servlet.http.HttpServletResponse;
import java.io.InputStream;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class ReportServiceImpl implements ReportService {
    @Autowired
    private WorkspaceService workspaceService;
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private OrderMapper orderMapper;
    @Override
    public TurnoverReportVO getTurnoverReport(LocalDate begin, LocalDate end) {
        long daysBetween = ChronoUnit.DAYS.between(begin, end);
        if (daysBetween > 90) {
            throw new IllegalArgumentException("查询时间范围不能超过90天");
        }
        // 1.datalist计算出来
        List<LocalDate> dateList = new ArrayList<>();// 开始日期到结束日期的日期列表
        dateList.add(begin);
        while(!begin.equals(end)){
            begin = begin.plusDays(1);// 日期加1
            dateList.add(begin);
        }
        // 2.turnoverList计算出来
        List<Double> turnoverList = new ArrayList<>();
        Map map = new HashMap();
        for(LocalDate date : dateList){
            LocalDateTime beginDateTime = LocalDateTime.of(date, LocalTime.MIN);
            LocalDateTime endDateTime = LocalDateTime.of(date, LocalTime.MAX);
            map.put("begin", beginDateTime);
            map.put("end", endDateTime);
            map.put("status", Orders.COMPLETED);
            Double turnover = orderMapper.sumByMap(map);
            turnover = turnover == null ? 0.0 : turnover;//  如果为null则赋值为0.0
            turnoverList.add(turnover);
        }
        // 3.封装成TurnoverReportVO并返回
        return TurnoverReportVO
                .builder()
                .dateList(StringUtils.join(dateList, ","))
                .turnoverList(StringUtils.join(turnoverList, ","))
                .build();


    }

    @Override
    public UserReportVO getUserReport(LocalDate begin, LocalDate end) {
        long daysBetween = ChronoUnit.DAYS.between(begin, end);
        if (daysBetween > 90) {
            throw new IllegalArgumentException("查询时间范围不能超过90天");
        }
        // 1.datalist计算出来
        List<LocalDate> dateList = new ArrayList<>();// 开始日期到结束日期的日期列表
        dateList.add(begin);

        while(!begin.equals(end)){
            begin = begin.plusDays(1);// 日期加1
            dateList.add(begin);
        }
        // 2.totalUserList计算出来
        List<Integer> totalUserList = new ArrayList<>();
        // 3.newUserList计算出来
        List<Integer> newUserList = new ArrayList<>();
        for(LocalDate date : dateList){
            LocalDateTime beginDateTime = LocalDateTime.of(date, LocalTime.MIN);
            LocalDateTime endDateTime = LocalDateTime.of(date, LocalTime.MAX);
            Map map = new HashMap();
            map.put("end", endDateTime);
            Integer totalUser = userMapper.countByMap(map);

            map.put("begin", beginDateTime);
            Integer newUser = userMapper.countByMap(map);// 新增用户数

            totalUserList.add(totalUser);
            newUserList.add(newUser);
        }
        // 4.封装成UserReportVO并返回
        return UserReportVO
                .builder()
                .dateList(StringUtils.join(dateList, ","))
                .totalUserList(StringUtils.join(totalUserList, ","))
                .newUserList(StringUtils.join(newUserList, ","))
                .build();
    }

    @Override
    public OrderReportVO getOrderReport(LocalDate begin, LocalDate end) {
        long daysBetween = ChronoUnit.DAYS.between(begin, end);
        if (daysBetween > 90) {
            throw new IllegalArgumentException("查询时间范围不能超过90天");
        }
        // 1.datalist计算出来
        List<LocalDate> dateList = new ArrayList<>();// 开始日期到结束日期的日期列表
        dateList.add(begin);

        while(!begin.equals(end)){
            begin = begin.plusDays(1);// 日期加1
            dateList.add(begin);
        }
        // 2.totalOrderCountList计算出来
        List<Integer> orderCountList = new ArrayList<>();
        // 3.validOrderCountList计算出来
        List<Integer> validOrderCountList = new ArrayList<>();
        // 4.orderCompletionRate计算出来
        List<Double> orderCompletionRateList = new ArrayList<>();
        for(LocalDate date : dateList){
            LocalDateTime beginDateTime = LocalDateTime.of(date, LocalTime.MIN);
            LocalDateTime endDateTime = LocalDateTime.of(date, LocalTime.MAX);

            Integer totalOrderCount = getOrderCount(beginDateTime, endDateTime, null);// 总订单数

            Integer validOrderCount = getOrderCount(beginDateTime, endDateTime, Orders.COMPLETED); // 有效订单数


            orderCountList.add(totalOrderCount);
            validOrderCountList.add(validOrderCount);
        }
        // 4.orderCompletionRate计算出来,  通过totalOrderCount和validOrderCount计算出来
        Integer totalOrderCount = orderCountList.stream().reduce(Integer::sum).get(); // 总订单数
        Integer validOrderCount = validOrderCountList.stream().reduce(Integer::sum).get(); // 有效订单数
        Double orderCompletionRate = totalOrderCount == 0 ? 0.0 : (double) validOrderCount / totalOrderCount; // 订单完成率

        // 5.封装成OrderReportVO并返回
        return OrderReportVO
                .builder()
                .dateList(StringUtils.join(dateList, ","))
                .orderCountList(StringUtils.join(orderCountList, ","))
                .validOrderCountList(StringUtils.join(validOrderCountList, ","))
                .totalOrderCount(totalOrderCount)
                .validOrderCount(validOrderCount)
                .orderCompletionRate(orderCompletionRate)
                .build();
    }

    @Override
    public SalesTop10ReportVO getSalesTop10Report(LocalDate begin, LocalDate end) {
        // 1.查询top10商品
        long daysBetween = ChronoUnit.DAYS.between(begin, end);
        if (daysBetween > 90) {
            throw new IllegalArgumentException("查询时间范围不能超过90天");
        }
        LocalDateTime beginTime = LocalDateTime.of(begin, LocalTime.MIN);
        LocalDateTime endTime = LocalDateTime.of(end, LocalTime.MAX);
        // 1.先查订单表
        List<GoodsSalesDTO> salesTop10 = orderMapper.getSalesTop(beginTime, endTime);

        // 2.封装成nameList和numberList
        List<String> nameList = salesTop10.stream().map(GoodsSalesDTO::getName).collect(Collectors.toList());
        List<Integer> numberList = salesTop10.stream().map(GoodsSalesDTO::getNumber).collect(Collectors.toList());

        // 23.封装成SalesTop10ReportVO并返回
        return SalesTop10ReportVO.builder()
                .nameList(StringUtils.join(nameList, ","))
                .numberList(StringUtils.join(numberList, ","))
                .build();

    }

    /**
     * 导出业务数据
     */
    @Override
    public void exportBusinessData(HttpServletResponse response) {
        LocalDate  dateBegin = LocalDate.now().minusDays(30);
        LocalDate  dateEnd = LocalDate.now().minusDays(1);
        // 1.查询所有订单,获取30天营业数据（概览数据和明细数据）
        BusinessDataVO businessData = workspaceService.getBusinessData(LocalDateTime.of(dateBegin, LocalTime.MIN), LocalDateTime.of(dateEnd, LocalTime.MAX)); //LocalDateTime.of()可以将LocalDate转换为LocalDateTime
        // 2.poi写入数据到excel文件并下载
        InputStream in = this.getClass().getClassLoader().getResourceAsStream("template/运营数据报表模板.xlsx");
        try  {
            XSSFWorkbook excel = new XSSFWorkbook(in);
            // 填充数据
            XSSFSheet sheet = excel.getSheet("sheet1");//  获取第一个sheet页
            sheet.getRow(1).getCell(1).setCellValue("时间：" + dateBegin + "至" + dateEnd);// 时间

            //获取第四行的单元格对象
            XSSFRow row = sheet.getRow(3);
            row.getCell(2).setCellValue(businessData.getTurnover());// 营业额
            row.getCell(4).setCellValue(businessData.getOrderCompletionRate());//  订单完成率
            row.getCell(6).setCellValue(businessData.getNewUsers());//  新增用户数

            // 获得第五行的单元格对象
            row = sheet.getRow(4);
            row.getCell(2).setCellValue(businessData.getValidOrderCount().toString());//  有效订单数
            row.getCell(4).setCellValue(businessData.getUnitPrice());//  平均客单价

            //填充明细数据
            for(int i=0;i<30;i++){
                LocalDate date = dateBegin.plusDays(i);
                //查询某一天天的订单数据
                BusinessDataVO data = workspaceService.getBusinessData(LocalDateTime.of(date, LocalTime.MIN), LocalDateTime.of(date, LocalTime.MAX));
                row = sheet.getRow(7+i);
                row.getCell(1).setCellValue(date.toString());// 日期
                row.getCell(2).setCellValue(data.getTurnover());// 营业额
                row.getCell(3).setCellValue(data.getValidOrderCount());//  有效订单数
                row.getCell(4).setCellValue(data.getOrderCompletionRate());//  订单完成率
                row.getCell(5).setCellValue(data.getUnitPrice());//  平均客单价
                row.getCell(6).setCellValue(data.getNewUsers());//  新增用户数
            }

            // 3.输出流下载文件到本地，response为HttpServletResponse对象,用于 设置响应头信息，实现文件下载
            ServletOutputStream out = response.getOutputStream();
            excel.write(out);

            // 关闭资源
            out.close();
            excel.close();
        } catch (Exception e){
            e.printStackTrace();
        }
    }

    /**
     * 获取订单数量
     * @param begin
     * @param end
     * @param status
     * @return
     */
    private Integer getOrderCount(LocalDateTime begin, LocalDateTime end, Integer status){
        Map map = new HashMap();
        map.put("begin", begin);
        map.put("end", end);
        map.put("status", status);
        return orderMapper.countByMap(map);
    }
}

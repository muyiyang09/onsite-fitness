package com.onsitefitness.service;

import com.onsitefitness.dto.CourseDTO;
import com.onsitefitness.dto.CoursePageQueryDTO;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.vo.CourseVO;

import java.util.List;

public interface CourseService {

    /**
     * 新增课程
     * @param courseDTO
     */
    void save(CourseDTO courseDTO);

    /**
     * 课程分页查询
     * @param coursePageQueryDTO
     * @return
     */
    PageResult pageQuery(CoursePageQueryDTO coursePageQueryDTO);

    /**
     * 批量删除课程
     * @param ids
     */
    void deleteBatch(List<Long> ids);

    /**
     * 根据id查询课程
     * @param id
     * @return
     */
    CourseVO getById(Long id);

    /**
     * 修改课程
     * @param courseDTO
     */
    void update(CourseDTO courseDTO);

    /**
     * 课程起售停售
     * @param status
     * @param id
     */
    void startOrStop(Integer status, Long id);

    /**
     * 根据分类id查询起售课程
     * @param categoryId
     * @return
     */
    List<CourseVO> list(Long categoryId);
}

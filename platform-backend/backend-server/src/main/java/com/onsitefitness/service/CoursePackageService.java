package com.onsitefitness.service;

import com.onsitefitness.dto.CoursePackageDTO;
import com.onsitefitness.dto.CoursePackagePageQueryDTO;
import com.onsitefitness.entity.Course;
import com.onsitefitness.entity.CoursePackage;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.vo.CoursePackageVO;

import java.util.List;

public interface CoursePackageService {

    /**
     * 新增套餐，同时保存套餐和课程的关联关系
     * @param coursePackageDTO
     */
    void save(CoursePackageDTO coursePackageDTO);

    /**
     * 分页查询套餐
     * @param coursePackagePageQueryDTO
     * @return
     */
    PageResult pageQuery(CoursePackagePageQueryDTO coursePackagePageQueryDTO);

    /**
     * 批量删除套餐
     * @param ids
     */
    void deleteBatch(List<Long> ids);

    /**
     * 根据id查询套餐（含课程列表）
     * @param id
     * @return
     */
    CoursePackageVO getById(Long id);

    /**
     * 修改套餐
     * @param coursePackageDTO
     */
    void update(CoursePackageDTO coursePackageDTO);

    /**
     * 套餐起售停售
     * @param status
     * @param id
     */
    void startOrStop(Integer status, Long id);

    /**
     * 根据分类id查询起售套餐
     * @param categoryId
     * @return
     */
    List<CoursePackage> list(Long categoryId);

    /**
     * 根据套餐id查询包含的课程列表
     * @param id
     * @return
     */
    List<Course> getCourseListByPackageId(Long id);
}

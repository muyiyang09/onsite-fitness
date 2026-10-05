package com.onsitefitness.service.impl;

import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.constant.StatusConstant;
import com.onsitefitness.dto.CourseDTO;
import com.onsitefitness.dto.CoursePageQueryDTO;
import com.onsitefitness.entity.Course;
import com.onsitefitness.entity.CoursePackage;
import com.onsitefitness.exception.DeletionNotAllowedException;
import com.onsitefitness.mapper.CourseMapper;
import com.onsitefitness.mapper.CoursePackageMapper;
import com.onsitefitness.mapper.PackageCourseMapper;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.service.CourseService;
import com.onsitefitness.vo.CourseVO;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
public class CourseServiceImpl implements CourseService {

    @Autowired
    private CourseMapper courseMapper;
    @Autowired
    private PackageCourseMapper packageCourseMapper;
    @Autowired
    private CoursePackageMapper coursePackageMapper;

    /**
     * 新增课程
     * @param courseDTO
     */
    @Override
    @Transactional
    public void save(CourseDTO courseDTO) {
        Course course = new Course();
        BeanUtils.copyProperties(courseDTO, course);
        courseMapper.insert(course);
    }

    /**
     * 课程分页查询
     * @param coursePageQueryDTO
     * @return
     */
    @Override
    public PageResult pageQuery(CoursePageQueryDTO coursePageQueryDTO) {
        PageHelper.startPage(coursePageQueryDTO.getPage(), coursePageQueryDTO.getPageSize());
        Page<CourseVO> page = courseMapper.pageQuery(coursePageQueryDTO);
        return new PageResult(page.getTotal(), page.getResult());
    }

    /**
     * 批量删除课程
     * @param ids
     */
    @Override
    @Transactional
    public void deleteBatch(List<Long> ids) {
        //判断课程是否能够被删除--是否存在起售的课程
        for (Long id : ids) {
            Course course = courseMapper.getById(id);
            if (StatusConstant.ENABLE == course.getStatus()) {
                //起售中的课程不能删除
                throw new DeletionNotAllowedException(MessageConstant.DISH_ON_SALE);
            }
        }
        //删除当前课程是否能够被删除--是否存在套餐关联
        List<Long> packageIds = packageCourseMapper.getPackageIdsByCourseIds(ids);
        if (packageIds != null && packageIds.size() > 0) {
            //当前套餐关联的课程不能删除
            throw new DeletionNotAllowedException(MessageConstant.DISH_BE_RELATED_BY_SETMEAL);
        }
        //删除课程数据
        courseMapper.deleteByIds(ids);
    }

    /**
     * 根据id查询课程
     * @param id
     * @return
     */
    @Override
    public CourseVO getById(Long id) {
        Course course = courseMapper.getById(id);
        CourseVO courseVO = new CourseVO();
        BeanUtils.copyProperties(course, courseVO);
        return courseVO;
    }

    /**
     * 修改课程
     * @param courseDTO
     */
    @Override
    public void update(CourseDTO courseDTO) {
        Course course = new Course();
        BeanUtils.copyProperties(courseDTO, course);
        courseMapper.update(course);
    }

    /**
     * 课程起售停售
     * @param status
     * @param id
     */
    @Override
    public void startOrStop(Integer status, Long id) {
        Course course = Course.builder().id(id).status(status).build();
        courseMapper.update(course);
        //停售课程，同时停售包含该课程的套餐
        if (StatusConstant.DISABLE == status) {
            List<Long> courseIds = new ArrayList<>();
            courseIds.add(id);
            List<Long> packageIds = packageCourseMapper.getPackageIdsByCourseIds(courseIds);
            if (packageIds != null && packageIds.size() > 0) {
                for (Long packageId : packageIds) {
                    CoursePackage coursePackage = CoursePackage.builder().id(packageId).status(status).build();
                    coursePackageMapper.update(coursePackage);
                }
            }
        }
    }

    /**
     * 根据分类id查询起售课程
     * @param categoryId
     * @return
     */
    @Override
    public List<CourseVO> list(Long categoryId) {
        Course course = Course.builder()
                .categoryId(categoryId)
                .status(StatusConstant.ENABLE)
                .build();
        return courseMapper.list(course);
    }
}

package com.onsitefitness.service.impl;

import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.constant.StatusConstant;
import com.onsitefitness.dto.CoursePackageDTO;
import com.onsitefitness.dto.CoursePackagePageQueryDTO;
import com.onsitefitness.entity.Course;
import com.onsitefitness.entity.CoursePackage;
import com.onsitefitness.entity.PackageCourse;
import com.onsitefitness.exception.DeletionNotAllowedException;
import com.onsitefitness.exception.SetmealEnableFailedException;
import com.onsitefitness.mapper.CourseMapper;
import com.onsitefitness.mapper.CoursePackageMapper;
import com.onsitefitness.mapper.PackageCourseMapper;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.service.CoursePackageService;
import com.onsitefitness.vo.CoursePackageVO;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
public class CoursePackageServiceImpl implements CoursePackageService {

    @Autowired
    private CoursePackageMapper coursePackageMapper;
    @Autowired
    private PackageCourseMapper packageCourseMapper;
    @Autowired
    private CourseMapper courseMapper;

    /**
     * 新增套餐，同时保存套餐和课程的关联关系
     * @param coursePackageDTO
     */
    @Override
    @Transactional
    public void save(CoursePackageDTO coursePackageDTO) {
        CoursePackage coursePackage = new CoursePackage();
        BeanUtils.copyProperties(coursePackageDTO, coursePackage);

        //向套餐表插入数据
        coursePackageMapper.insert(coursePackage);

        //获取生成的套餐id
        Long packageId = coursePackage.getId();

        List<PackageCourse> packageCourses = coursePackageDTO.getCourses();
        if (packageCourses != null && packageCourses.size() > 0) {
            packageCourses.forEach(pc -> pc.setPackageId(packageId));
            //保存套餐和课程的关联关系
            packageCourseMapper.insertBatch(packageCourses);
        }
    }

    /**
     * 分页查询套餐
     * @param coursePackagePageQueryDTO
     * @return
     */
    @Override
    public PageResult pageQuery(CoursePackagePageQueryDTO coursePackagePageQueryDTO) {
        int pageNum = coursePackagePageQueryDTO.getPage();
        int pageSize = coursePackagePageQueryDTO.getPageSize();

        PageHelper.startPage(pageNum, pageSize);
        Page<CoursePackageVO> page = coursePackageMapper.pageQuery(coursePackagePageQueryDTO);
        return new PageResult(page.getTotal(), page.getResult());
    }

    /**
     * 批量删除套餐
     * @param ids
     */
    @Override
    @Transactional
    public void deleteBatch(List<Long> ids) {
        ids.forEach(id -> {
            CoursePackage coursePackage = coursePackageMapper.getById(id);
            if (StatusConstant.ENABLE == coursePackage.getStatus()) {
                //起售中的套餐不能删除
                throw new DeletionNotAllowedException(MessageConstant.SETMEAL_ON_SALE);
            }
        });

        ids.forEach(packageId -> {
            //删除套餐表中的数据
            coursePackageMapper.deleteById(packageId);
            //删除套餐课程关联表中的数据
            packageCourseMapper.deleteByPackageId(packageId);
        });
    }

    /**
     * 根据id查询套餐（含课程列表）
     * @param id
     * @return
     */
    @Override
    public CoursePackageVO getById(Long id) {
        CoursePackage coursePackage = coursePackageMapper.getById(id);
        List<PackageCourse> packageCourses = packageCourseMapper.getByPackageId(id);

        List<Course> courses = new ArrayList<>();
        if (packageCourses != null && packageCourses.size() > 0) {
            for (PackageCourse pc : packageCourses) {
                Course course = courseMapper.getById(pc.getCourseId());
                if (course != null) {
                    courses.add(course);
                }
            }
        }

        CoursePackageVO coursePackageVO = new CoursePackageVO();
        BeanUtils.copyProperties(coursePackage, coursePackageVO);
        coursePackageVO.setCourses(courses);

        return coursePackageVO;
    }

    /**
     * 修改套餐
     * @param coursePackageDTO
     */
    @Override
    @Transactional
    public void update(CoursePackageDTO coursePackageDTO) {
        CoursePackage coursePackage = new CoursePackage();
        BeanUtils.copyProperties(coursePackageDTO, coursePackage);

        //1、修改套餐表，执行update
        coursePackageMapper.update(coursePackage);

        //套餐id
        Long packageId = coursePackageDTO.getId();

        //2、删除套餐和课程的关联关系，操作package_course表，执行delete
        packageCourseMapper.deleteByPackageId(packageId);

        List<PackageCourse> packageCourses = coursePackageDTO.getCourses();
        if (packageCourses != null && packageCourses.size() > 0) {
            packageCourses.forEach(pc -> pc.setPackageId(packageId));
            //3、重新插入套餐和课程的关联关系，操作package_course表，执行insert
            packageCourseMapper.insertBatch(packageCourses);
        }
    }

    /**
     * 启用或停用套餐
     * @param status
     * @param id
     */
    @Override
    public void startOrStop(Integer status, Long id) {
        //起售套餐时，判断套餐内是否有停售课程，有停售课程提示"套餐内包含未启售课程，无法启售"
        if (StatusConstant.ENABLE == status) {
            List<PackageCourse> packageCourses = packageCourseMapper.getByPackageId(id);
            if (packageCourses != null && packageCourses.size() > 0) {
                for (PackageCourse pc : packageCourses) {
                    Course course = courseMapper.getById(pc.getCourseId());
                    if (course != null && StatusConstant.DISABLE == course.getStatus()) {
                        throw new SetmealEnableFailedException(MessageConstant.SETMEAL_ENABLE_FAILED);
                    }
                }
            }
        }

        CoursePackage coursePackage = CoursePackage.builder()
                .id(id)
                .status(status)
                .build();
        coursePackageMapper.update(coursePackage);
    }

    /**
     * 根据分类id查询起售套餐
     * @param categoryId
     * @return
     */
    @Override
    public List<CoursePackage> list(Long categoryId) {
        CoursePackage coursePackage = CoursePackage.builder()
                .categoryId(categoryId)
                .status(StatusConstant.ENABLE)
                .build();
        return coursePackageMapper.list(coursePackage);
    }

    /**
     * 根据套餐id查询包含的课程列表
     * @param id
     * @return
     */
    @Override
    public List<Course> getCourseListByPackageId(Long id) {
        List<PackageCourse> packageCourses = packageCourseMapper.getByPackageId(id);
        List<Course> courses = new ArrayList<>();
        if (packageCourses != null && packageCourses.size() > 0) {
            for (PackageCourse pc : packageCourses) {
                Course course = courseMapper.getById(pc.getCourseId());
                if (course != null) {
                    courses.add(course);
                }
            }
        }
        return courses;
    }
}

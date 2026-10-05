package com.onsitefitness.mapper;

import com.github.pagehelper.Page;
import com.onsitefitness.annotation.AutoFill;
import com.onsitefitness.dto.CoursePageQueryDTO;
import com.onsitefitness.entity.Course;
import com.onsitefitness.enumeration.OperationType;
import com.onsitefitness.vo.CourseVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface CourseMapper {

    /**
     * 根据分类id查询课程数量
     * @param categoryId
     * @return
     */
    @Select("select count(id) from course where category_id = #{categoryId}")
    Integer countByCategoryId(Long categoryId);

    /**
     * 插入课程数据
     * @param course
     */
    @AutoFill(value = OperationType.INSERT)
    void insert(Course course);

    /**
     * 分页查询课程
     * @param coursePageQueryDTO
     * @return
     */
    Page<CourseVO> pageQuery(CoursePageQueryDTO coursePageQueryDTO);

    /**
     * 批量删除课程
     * @param ids
     */
    void deleteByIds(List<Long> ids);

    /**
     * 根据id查询课程
     * @param id
     * @return
     */
    @Select("select * from course where id = #{id}")
    Course getById(Long id);

    /**
     * 更新课程数据
     * @param course
     */
    @AutoFill(value = OperationType.UPDATE)
    void update(Course course);

    /**
     * 动态条件查询课程（含分类名称）
     * @param course
     * @return
     */
    List<CourseVO> list(Course course);

    /**
     * 根据条件统计课程数量
     * @param map
     * @return
     */
    Integer countByMap(Map map);
}

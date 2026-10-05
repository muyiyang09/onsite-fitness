package com.onsitefitness.mapper;

import com.github.pagehelper.Page;
import com.onsitefitness.annotation.AutoFill;
import com.onsitefitness.dto.CoursePackagePageQueryDTO;
import com.onsitefitness.entity.CoursePackage;
import com.onsitefitness.enumeration.OperationType;
import com.onsitefitness.vo.CoursePackageVO;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface CoursePackageMapper {

    /**
     * 根据分类id查询套餐的数量
     * @param categoryId
     * @return
     */
    @Select("select count(id) from course_package where category_id = #{categoryId}")
    Integer countByCategoryId(Long categoryId);

    /**
     * 新增套餐
     * @param coursePackage
     */
    @AutoFill(value = OperationType.INSERT)
    void insert(CoursePackage coursePackage);

    /**
     * 分页查询套餐
     * @param coursePackagePageQueryDTO
     * @return
     */
    Page<CoursePackageVO> pageQuery(CoursePackagePageQueryDTO coursePackagePageQueryDTO);

    /**
     * 根据id查询套餐
     * @param id
     * @return
     */
    @Select("select * from course_package where id = #{id}")
    CoursePackage getById(Long id);

    /**
     * 更新套餐
     * @param coursePackage
     */
    @AutoFill(value = OperationType.UPDATE)
    void update(CoursePackage coursePackage);

    /**
     * 根据id删除套餐
     * @param id
     */
    @Delete("delete from course_package where id = #{id}")
    void deleteById(Long id);

    /**
     * 动态条件查询套餐
     * @param coursePackage
     * @return
     */
    List<CoursePackage> list(CoursePackage coursePackage);

    /**
     * 根据条件统计套餐数量
     * @param map
     * @return
     */
    Integer countByMap(Map map);
}

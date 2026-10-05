package com.onsitefitness.mapper;

import com.onsitefitness.entity.PackageCourse;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface PackageCourseMapper {

    /**
     * 批量插入套餐课程关联
     * @param packageCourses
     */
    void insertBatch(List<PackageCourse> packageCourses);

    /**
     * 根据套餐id删除套餐和课程的关联关系
     * @param packageId
     */
    @Delete("delete from package_course where package_id = #{packageId}")
    void deleteByPackageId(Long packageId);

    /**
     * 根据套餐id查询套餐和课程的关联关系
     * @param packageId
     * @return
     */
    @Select("select * from package_course where package_id = #{packageId}")
    List<PackageCourse> getByPackageId(Long packageId);

    /**
     * 根据课程id列表查询关联的套餐id
     * @param courseIds
     * @return
     */
    List<Long> getPackageIdsByCourseIds(List<Long> courseIds);
}

package com.onsitefitness.mapper;

import com.onsitefitness.entity.User;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.Map;

@Mapper
public interface UserMapper {
    /**
     * 根据openId查询用户信息
     * @param openId
     * @return
     */
    @Select("SELECT * FROM user WHERE openid = #{openId}")
    User getByOpenId(String openId);

    /**
     * 插入用户信息
     * @param user
     */
    void insert(User user);

    /**
     * 根据用户id查询用户信息
     * @param id
     * @return
     */
    @Select("SELECT * FROM user WHERE id = #{id}")
    User getById(Long id);

    /**
     * 根据条件查询用户数量
     * @param map
     * @return
     */
    Integer countByMap(Map map);
}

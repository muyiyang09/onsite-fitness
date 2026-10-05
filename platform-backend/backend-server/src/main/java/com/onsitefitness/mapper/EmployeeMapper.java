package com.onsitefitness.mapper;

import com.github.pagehelper.Page;
import com.onsitefitness.annotation.AutoFill;
import com.onsitefitness.dto.EmployeePageQueryDTO;
import com.onsitefitness.dto.PasswordEditDTO;
import com.onsitefitness.entity.Employee;
import com.onsitefitness.enumeration.OperationType;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface EmployeeMapper {

    /**
     * 根据用户名查询员工
     * @param username
     * @return
     */
    @Select("select * from employee where username = #{username}")
    Employee getByUsername(String username);

    /**
     * 新增员工
     * @param employee
     */
    @Insert("insert into employee (username, name, password, phone, sex, id_number, status, create_time, update_time, create_user, update_user) " +
            "values (#{username}, #{name}, #{password}, #{phone}, #{sex}, #{idNumber}, #{status}, #{createTime}, #{updateTime}, #{createUser}, #{updateUser})")
    @AutoFill(value = OperationType.INSERT)
    void insert(Employee employee);

    /**
     * 分页查询员工
     * @param employeePageQueryDTO
     * @return
     */
    Page<Employee> pageQuery(EmployeePageQueryDTO employeePageQueryDTO);

    /**
     * 启用禁用员工账号
     * @param employee
     */
    @AutoFill(value = OperationType.UPDATE)
    void update(Employee employee);

    @Select("select * from employee where id = #{id}")
    Employee selectByPrimaryKey(Long id);

    /**
     * 修改员工密码
     * @param passwordEditDTO
     */
    @Update("update employee set password = #{newPassword} where id = #{empId} and password = #{oldPassword}")
    void updatePassword(PasswordEditDTO passwordEditDTO);
}

package com.onsitefitness.service;

import com.onsitefitness.dto.EmployeeDTO;
import com.onsitefitness.dto.EmployeeLoginDTO;
import com.onsitefitness.dto.EmployeePageQueryDTO;
import com.onsitefitness.dto.PasswordEditDTO;
import com.onsitefitness.entity.Employee;
import com.onsitefitness.result.PageResult;

public interface EmployeeService {

    /**
     * 员工登录
     * @param employeeLoginDTO
     * @return
     */
    Employee login(EmployeeLoginDTO employeeLoginDTO);

    void save(EmployeeDTO employeeDTO);

    PageResult pageQuery(EmployeePageQueryDTO employeePageQueryDTO);

    void startOrStop(Integer status, Long id);

    Employee getById(Long id);

    void update(EmployeeDTO employeeDTO);

    /**
     * 修改密码
     * @param passwordEditDTO
     */
    void editPassword(PasswordEditDTO passwordEditDTO);
}

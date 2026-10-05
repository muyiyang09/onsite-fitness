package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 教练登录 DTO
 */
@Data
public class CoachLoginDTO implements Serializable {

    private String phone;

    private String password;

}

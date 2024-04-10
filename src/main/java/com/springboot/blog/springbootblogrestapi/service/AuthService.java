package com.springboot.blog.springbootblogrestapi.service;

import com.springboot.blog.springbootblogrestapi.payload.LoginDto;
import com.springboot.blog.springbootblogrestapi.payload.RegisterDto;

public interface AuthService {
    String login(LoginDto logindto);

    String register(RegisterDto registerDto);
}

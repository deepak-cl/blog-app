package com.springboot.blog.springbootblogrestapi.repository;

import com.springboot.blog.springbootblogrestapi.entity.Post;
import org.springframework.data.jpa.repository.JpaRepository;

// we don't need to add @Repository annotation to this interface because the JPARepository interface has an implementation class
// called SimpleRepository
// Post repository for Post Entity
public interface PostRepository extends JpaRepository<Post, Long> {
    //
}
